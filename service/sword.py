"""
SWORDv2 API implementation for SSS

This provides an implenentation of sss.core.SwordServer and related support classes which implements the features that are used by this
module.
"""

from sss.core import SwordServer, ServiceDocument, SDCollection, SwordError, Authenticator, Auth, DepositResponse, EntryDocument, Statement, MediaResourceResponse
from sss.spec import Errors
from flask import url_for
from octopus.modules.jper import client, models
from octopus.core import app

class JperAuth(Auth):
    """
    Implementation of the sss.core.Auth class, which represents the authentication information
    (username, password, on-behalf-of user).
    """
    def __init__(self, username=None, on_behalf_of=None, password=None):
        super(JperAuth, self).__init__(username=username, on_behalf_of=on_behalf_of)
        self.password = password

class JperAuthenticator(Authenticator):
    """
    Implementation of the sss.core.Authenticator class, which provides a hook for basic authentication
    to be implemented
    """
    def __init__(self, config):
        super(JperAuthenticator, self).__init__(config)

    def basic_authenticate(self, username, password, obo):
        """
        Basic authenticate the user.  Though in reality this does nothing.

        Since the actual authentication will be done at JPER rather than here, all we need to do
        is create a JperAuth object and let that service bounce the response if the creds are wrong

        :param username:    the username
        :param password: the password
        :param obo: not used - here for method sig compliance on superclass
        :return: a JperAuth object representing these
        """
        # we don't even attempt to auth the user, just let the
        # JPER API do that
        app.logger.debug(u"Request received for Basic Auth on Username:{x} - credentials to be forwarded to JPER, not checked here".format(x=username))
        return JperAuth(username, obo, password)

class JperSword(SwordServer):
    """
    Implementation of the sss.core.SwordServer which provides implementations only for the methods
    supported by JPER
    """
    def __init__(self, config, auth):
        super(JperSword, self).__init__(config, auth)

        # create a URIManager for us to use
        self.um = URIManager(self.configuration)

        # instance of the jper client to communicate via
        self.jper = client.JPER(api_key=self.auth_credentials.password)

        # a place to cache the notes we retrieve from the server
        self.notes = {}

    ##############################################
    ## Methods required by the JPER integration

    def container_exists(self, path):
        """
        Does the url path provided refer to a notification that already exists?

        Note that this queries the JPER API and caches a copy of the notification

        :param path: url path (e.g. the notification id)
        :return: True if the notification exists, False if not
        """
        app.logger.info(u"Request received to check existence of Notification:{x}".format(x=path))
        return self._cache_notification(path)

    def media_resource_exists(self, path):
        """
        Does the media resource (content file) as referenced by the url path exist

        Note that this queries the JPER API and caches a copy of the notification

        :param path: url path for the notification content file
        :return: True if the file exists, False if not
        """
        app.logger.info(u"Request received to check existence of Media Resource for Notification:{x}".format(x=path))
        cached = self._cache_notification(path)
        if not cached:
            app.logger.info(u"Unable to retrieve and cache Notification:{x}".format(x=path))
            return False

        # get the note from the cache
        note = self.notes[path]

        # a note has a media resource if there is a content link associated with it
        packs = note.get_urls(type="package")
        if len(packs) == 0:
            app.logger.info(u"No Media Resource available for Notification:{x}".format(x=path))
        else:
            app.logger.info(u"One or more Media Resources found for Notification:{x}".format(x=path))
        return len(packs) > 0

    def service_document(self, path=None):
        """
        Construct the Service Document for JPER.  This takes the set of collections that are in the store, and places them in
        an Atom Service document as the individual entries

        This will provide two collections for deposit: one for validation requests and the other for create requests.

        :param path: url path sent to the server (for supporting sub-service documents, which we don't in this implementation)
        :return: serialised service document
        """
        app.logger.info(u"Request received for SWORD Service Document")
        service = ServiceDocument(version=self.configuration.sword_version,
                                    max_upload_size=self.configuration.max_upload_size)

        # Our service document always consists of exactly 2 collections - one for validation
        # and the other for actual deposit

        accept = self.configuration.app_accept
        multipart_accept = self.configuration.multipart_accept
        accept_package = self.configuration.sword_accept_package

        validate = SDCollection(
            href=self.um.col_uri("validate"),
            title="Validate",
            accept=accept,
            multipart_accept=multipart_accept,
            description="Deposit here to validate the format of your notification files",
            accept_package=accept_package,
            collection_policy="This collection will take any deposit package intended for the Router",
            mediation=self.configuration.mediation,
            treatment="Packages sent here will be validated, and you will receive an error document or a deposit receipt.  " +
                      "The deposit will not subsequently be stored, so you will not be able to retrieve it again afterwards.",
            sub_service=[]
        )

        notify = SDCollection(
            href=self.um.col_uri("notify"),
            title="Notify",
            accept=accept,
            multipart_accept=multipart_accept,
            description="Deposit here to deliver a publication event notification",
            accept_package=accept_package,
            collection_policy="This collection will take any deposit package intended for the Router",
            mediation=self.configuration.mediation,
            treatment="Packages sent here will be analysed for metadata suitable for routing to appropriate repository systems, " +
                      "and then delivered onward.",
            sub_service=[]
        )

        # service.add_workspace("JPER", [validate, notify])
        # 2016-10-25 TD : title adjustment of the Service-Document for DeepGreen
        service.add_workspace("DeepGreen Prototype", [validate, notify])

        # serialise and return
        return service.serialise()

    def deposit_new(self, path, deposit):
        """
        Take the supplied deposit and treat it as a new container with content to be created in the specified collection path

        :param path:    the ID of the collection to be deposited into
        :param deposit:       the DepositRequest object to be processed
        :return: a DepositResponse object which will contain the Deposit Receipt or a SWORD Error
        """
        app.logger.info(u"Request received to deposit new notification to Location:{x}".format(x=path))

        # make a notification that we can use to go along with the deposit
        # it doesn't need to contain anything
        notification = models.IncomingNotification()
        notification.packaging_format = deposit.packaging

        # instance of the jper client to communicate via
        jper = client.JPER(api_key=deposit.auth.password)

        # the deposit could be on the validate or the notify endpoint
        receipt = None
        loc = None
        accepted = False
        create = False
        if path == "validate":
            try:
                jper.validate(notification, file_handle=deposit.content_file)
            except client.JPERAuthException as e:
                app.logger.debug(u"User provided invalid authentication credentials for JPER")
                raise SwordError(status=401, empty=True)
            except client.ValidationException as e:
                app.logger.debug("Validation failed for user's notification")
                raise SwordError(error_uri=Errors.bad_request, msg=e.message, author="JPER", treatment="validation failed")
            app.logger.debug("Validation succeeded on user's notification")
            accepted = True
        elif path == "notify":
            try:
                id, loc = jper.create_notification(notification, file_handle=deposit.content_file)
                receipt = self._make_receipt(id, deposit.packaging, "Notification has been accepted for routing")
            except client.JPERAuthException as e:
                app.logger.debug(u"User provided invalid authentication credentials for JPER")
                raise SwordError(status=401, empty=True)
            except client.ValidationException as e:
                app.logger.debug("Validation failed for user's notification")
                raise SwordError(error_uri=Errors.bad_request, msg=e.message, author="JPER", treatment="validation failed")
            app.logger.debug("Create succeeded on user's notification")
            create = True
        else:
            app.logger.debug(u"Create request was not made to a valid endpoint")
            raise SwordError(status=404, empty=True)

        # finally, assemble the deposit response and return
        dr = DepositResponse()
        if receipt is not None:
            dr.receipt = receipt.serialise()
        if loc is not None:
            dr.location = loc

        if accepted:
            dr.accepted = True
        elif create:
            dr.created = True

        return dr

    def get_media_resource(self, path, accept_parameters):
        """
        Get a representation of the media resource for the given id as represented by the specified content type

        :param id:    The ID of the object in the store
        :param content_type   A ContentType object describing the type of the object to be retrieved
        :return: the media resource wrapped in a MediaResourceResponse object
        """
        app.logger.info(u"Request received to retrieve Media Resource from Notification:{x}".format(x=path))
        cached = self._cache_notification(path)
        if not cached:
            app.logger.debug(u"Unable to retrieve and cache Notification:{x}".format(x=path))
            raise SwordError(status=404, empty=True)

        # get the note from the cache
        note = self.notes[path]

        # a note has a media resource if there is a content link associated with it
        packs = note.get_urls(type="package")
        if len(packs) == 0:
            app.logger.debug(u"No Media Resource associated with Notification:{x}".format(x=path))
            raise SwordError(status=404, empty=True)

        mr = MediaResourceResponse()
        mr.redirect = True
        mr.url = packs[0]
        app.logger.debug(u"Returned Media Resource:{x}".format(x=packs[0]))
        return mr

    def get_container(self, path, accept_parameters):
        """
        Get a representation of the container in the requested content type

        :param path:   The ID of the object in the store
        :param accept_parameters:   An AcceptParameters object describing the required format
        :return: a representation of the container in the appropriate format
        """
        app.logger.info(u"Received request to retrieve Notification:{x}".format(x=path))

        # by the time this is called, we should already know that we can return this type, so there is no need for
        # any checking, we just get on with it

        # pick either the deposit receipt or the pure statement to return to the client
        if accept_parameters.content_type.mimetype() == "application/atom+xml;type=entry":
            app.logger.info(u"Returning deposit receipt for Notification:{x}".format(x=path))
            return self._get_deposit_receipt(path)
        else:
            app.logger.info(u"Returning statement for Notification:{x}".format(x=path))
            return self.get_statement(path, accept_parameters.content_type.mimetype())

    def get_statement(self, path, type=None):
        """
        Get a representation of the container and its current state as a sword statement

        :param path: the id of the object in the store
        :param type: the mimetype of statement to return
        :return: a serialised statement in the appropriate format
        """
        if type is None:
            type = "application/atom+xml;type=feed"
        app.logger.info(u"Received request for Statement for Notification:{x} in Mimetype:{y}".format(x=path, y=type))

        cached = self._cache_notification(path)
        if not cached:
            app.logger.debug(u"Unable to retrieve and cache Notification:{x}".format(x=path))
            raise SwordError(status=404, empty=True)
        note = self.notes[path]

        # State information
        #state_uri = "http://router2.mimas.ac.uk/swordv2/state/pending"
        state_uri = "http://datahub.deepgreen.org/sword/state/pending"
        state_description = "Notification has been accepted for routing"
        ad = note.analysis_date
        if ad is not None:
            # state_uri = "http://router2.mimas.ac.uk/swordv2/state/routed"
            state_uri = "http://datahub.deepgreen.org/sword/state/routed"
            state_description = "Notification has been routed for appropriate repositories"

        # the derived resources/provided links
        derived_resources = [l.get("url") for l in note.links]

        # the various urls
        agg_uri = self.um.agg_uri(path)
        edit_uri = self.um.edit_uri(path)
        deposit_uri = self.um.cont_uri(path)

        # depositing user
        by = self.auth_credentials.username
        obo = self.auth_credentials.on_behalf_of

        # create the new statement
        s = Statement()
        s.aggregation_uri = agg_uri
        s.rem_uri = edit_uri
        s.original_deposit(deposit_uri, note.created_datestamp, note.packaging_format, by, obo)
        s.add_state(state_uri, state_description)
        s.aggregates = derived_resources

        # now serve the relevant serialisation
        if type == "application/rdf+xml":
            app.logger.debug(u"Returning RDF/XML Statement for Notification:{x}".format(x=path))
            return s.serialise_rdf()
        elif type == "application/atom+xml;type=feed":
            app.logger.debug(u"Returning ATOM Feed Statement for Notification:{x}".format(x=path))
            return s.serialise_atom()
        else:
            app.logger.debug(u"Mimetype unrecognised, so not returning Statement for Notification:{x}".format(x=path))
            return None


    #############################################
    ## some internal methods

    def _cache_notification(self, path):
        """
        Get a copy of the notification specified by the path, and store a copy of it
        in memory for fast access later

        :param path:
        :return: True if exists, False if not
        """
        # if we haven't got a cached copy, get one
        if path not in self.notes:
            note = self.jper.get_notification(notification_id=path)
            if note is not None:
                # cache the result
                self.notes[path] = note
            else:
                return False
        return True

    def _make_receipt(self, id, packaging, treatment):
        """
        Create an EntryDocument representing the notification with the specified identifier, packaging and treatment

        :param id: id of the notification
        :param packaging: packaging format of any associated binary content
        :param treatment: human readable text explaining what we did to the notification on ingest
        :return: an EntryDocument suitable for use as a deposit reciept
        """
        receipt = EntryDocument()
        receipt.atom_id = self.um.atom_id(id)
        receipt.content_uri = self.um.cont_uri(id)
        receipt.edit_uri = self.um.edit_uri(id)
        receipt.em_uris = [(self.um.em_uri(id), "application/zip")]
        receipt.packaging = [packaging]
        receipt.state_uris = [(self.um.state_uri(id, "atom"), "application/atom+xml;type=feed"), (self.um.state_uri(id, "rdf"), "application/rdf+xml")]
        receipt.generator = self.configuration.generator
        receipt.treatment = treatment
        receipt.original_deposit_uri = self.um.em_uri(id)
        return receipt

    def _get_deposit_receipt(self, path):
        """
        Get a deposit receipt for the notificiation identified by the path

        :param path: notification id
        :return: serialised deposit receipt
        """
        cached = self._cache_notification(path)
        if not cached:
            raise SwordError(status=404, empty=True)
        note = self.notes[path]
        ad = note.analysis_date
        treatment = "Notification has been accepted for routing"
        if ad is not None:
            treatment = "Notification has been routed for appropriate repositories"
        receipt = self._make_receipt(note.id, note.packaging_format, treatment)
        return receipt.serialise()


    #############################################
    ## Methods not currently required by the JPER
    ## Integration, and which are therefore not implemented
    ## Left here to remind us

    def list_collection(self, path):
        """
        NOT IMPLEMENTED
        """
        raise NotImplementedError()

    def replace(self, path, deposit):
        """
        NOT IMPLEMENTED
        """
        raise NotImplementedError()

    def delete_content(self, path, delete):
        """
        NOT IMPLEMENTED
        """
        raise NotImplementedError()

    def add_content(self, path, deposit):
        """
        NOT IMPLEMENTED
        """
        raise NotImplementedError()

    def deposit_existing(self, path, deposit):
        """
        NOT IMPLEMENTED
        """
        raise NotImplementedError()

    def delete_container(self, path, delete):
        """
        NOT IMPLEMENTED
        """
        raise NotImplementedError()


class URIManager(object):
    """
    Class for providing a single point of access to all identifiers used by SSS
    """
    def __init__(self, config):
        self.configuration = config

    def atom_id(self, id):
        """
        Format the notification ID to use for Atom Entries

        :param id: the notification id
        :return: a tag identifier for use in atom
        """
        return "tag:container@jper/" + id

    def sd_uri(self):
        """
        Get the service document URL

        :return: the url for the service doc
        """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.service_document")

    def col_uri(self, id):
        """
        The url for a collection on the server

        :param id: the id of the collection (validate/notify)
        :return: the url to the collection
        """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.collection", collection_id=id)

    def edit_uri(self, id):
        """
        The Edit-URI for a notification

        :param id: the id of the notification
        :return: the url for the container
        """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.entry", entry_id=id)

    def em_uri(self, id):
        """
        The EM-URI for the notification

        :param id: the id of the notification
        :return: the url for media resource in the container
        """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.content", entry_id=id)

    def cont_uri(self, id):
        """
        The Cont-URI for the notification

        :param id: the id of the notification
        :return: the url for content identifier in the container
        """
        return self.em_uri(id)

    def state_uri(self, id, type):
        """
        The Statement URL for the notification

        :param id: the id of the notification
        :param type: the type of statement (e.g. atom/rdf)
        :return: the url for the statment
        """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.statement", entry_id=id, type=type)

    def agg_uri(self, id):
        """
        Aggregation Tag URI for use in RDF statement

        :param id: id of the notification
        :return: tag uri for use in RDF graphs
        """
        return "tag:aggregation@jper/" + id

