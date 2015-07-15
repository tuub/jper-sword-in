from sss.core import SwordServer, ServiceDocument, SDCollection, SwordError, Authenticator, Auth, DepositResponse, EntryDocument, Statement, MediaResourceResponse
from sss.spec import Errors
from flask import url_for
from octopus.modules.jper import client, models

class JperAuth(Auth):

    def __init__(self, username=None, on_behalf_of=None, password=None):
        super(JperAuth, self).__init__(username=username, on_behalf_of=on_behalf_of)
        self.password = password

class JperAuthenticator(Authenticator):

    def __init__(self, config):
        super(JperAuthenticator, self).__init__(config)

    def basic_authenticate(self, username, password, obo):
        # we don't even attempt to auth the user, just let the
        # JPER API do that
        return JperAuth(username, obo, password)

class JperSword(SwordServer):

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
        return self._cache_notification(path)

    def media_resource_exists(self, path):
        cached = self._cache_notification(path)
        if not cached:
            return False

        # get the note from the cache
        note = self.notes[path]

        # a note has a media resource if there is a content link associated with it
        packs = note.get_urls(type="package")
        return len(packs) > 0

    def service_document(self, path=None):
        """
        Construct the Service Document.  This takes the set of collections that are in the store, and places them in
        an Atom Service document as the individual entries
        """
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

        service.add_workspace("JPER", [validate, notify])

        # serialise and return
        return service.serialise()

    def deposit_new(self, path, deposit):
        """
        Take the supplied deposit and treat it as a new container with content to be created in the specified collection
        Args:
        -path:    the ID of the collection to be deposited into
        -deposit:       the DepositRequest object to be processed
        Returns a DepositResponse object which will contain the Deposit Receipt or a SWORD Error
        """
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
                raise SwordError(status=401, empty=True)
            except client.ValidationException as e:
                raise SwordError(error_uri=Errors.bad_request, msg=e.message, author="JPER", treatment="validation failed")
            accepted = True
        elif path == "notify":
            try:
                id, loc = jper.create_notification(notification, file_handle=deposit.content_file)
                receipt = self._make_receipt(id, deposit.packaging, "Notification has been accepted for routing")
            except client.JPERAuthException as e:
                raise SwordError(status=401, empty=True)
            except client.ValidationException as e:
                raise SwordError(error_uri=Errors.bad_request, msg=e.message, author="JPER", treatment="validation failed")
            create = True
        else:
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
        -id:    The ID of the object in the store
        -content_type   A ContentType object describing the type of the object to be retrieved
        """
        cached = self._cache_notification(path)
        if not cached:
            raise SwordError(status=404, empty=True)

        # get the note from the cache
        note = self.notes[path]

        # a note has a media resource if there is a content link associated with it
        packs = note.get_urls(type="package")
        if len(packs) == 0:
            raise SwordError(status=404, empty=True)

        mr = MediaResourceResponse()
        mr.redirect = True
        mr.url = packs[0]
        return mr

    def get_container(self, path, accept_parameters):
        """
        Get a representation of the container in the requested content type
        Args:
        -path:   The ID of the object in the store
        -accept_parameters   An AcceptParameters object describing the required format
        Returns a representation of the container in the appropriate format
        """
        # by the time this is called, we should already know that we can return this type, so there is no need for
        # any checking, we just get on with it

        # pick either the deposit receipt or the pure statement to return to the client
        if accept_parameters.content_type.mimetype() == "application/atom+xml;type=entry":
            return self._get_deposit_receipt(path)
        else:
            return self.get_statement(path, accept_parameters.content_type.mimetype())

    def get_statement(self, path, type=None):
        if type is None:
            type = "application/atom+xml;type=feed"

        cached = self._cache_notification(path)
        if not cached:
            raise SwordError(status=404, empty=True)
        note = self.notes[path]

        # State information
        state_uri = "http://router2.mimas.ac.uk/swordv2/state/pending"
        state_description = "Notification has been accepted for routing"
        ad = note.analysis_date
        if ad is not None:
            state_uri = "http://router2.mimas.ac.uk/swordv2/state/routed"
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
            return s.serialise_rdf()
        elif type == "application/atom+xml;type=feed":
            return s.serialise_atom()
        else:
            return None


    #############################################
    ## some internal methods

    def _cache_notification(self, path):
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
        List the contents of a collection identified by the supplied id
        """
        raise NotImplementedError()

    def replace(self, path, deposit):
        """
        Replace all the content represented by the supplied id with the supplied deposit
        Args:
        - oid:  the object ID in the store
        - deposit:  a DepositRequest object
        Return a DepositResponse containing the Deposit Receipt or a SWORD Error
        """
        raise NotImplementedError()

    def delete_content(self, path, delete):
        """
        Delete all of the content from the object identified by the supplied id.  the parameters of the delete
        request must also be supplied
        - oid:  The ID of the object to delete the contents of
        - delete:   The DeleteRequest object
        Return a DeleteResponse containing the Deposit Receipt or the SWORD Error
        """
        raise NotImplementedError()

    def add_content(self, path, deposit):
        """
        Take the supplied deposit and treat it as a new container with content to be created in the specified collection
        Args:
        -collection:    the ID of the collection to be deposited into
        -deposit:       the DepositRequest object to be processed
        Returns a DepositResponse object which will contain the Deposit Receipt or a SWORD Error
        """
        raise NotImplementedError()

    def deposit_existing(self, path, deposit):
        """
        Deposit the incoming content into an existing object as identified by the supplied identifier
        Args:
        -oid:   The ID of the object we are depositing into
        -deposit:   The DepositRequest object
        Returns a DepositResponse containing the Deposit Receipt or a SWORD Error
        """
        raise NotImplementedError()

    def delete_container(self, path, delete):
        """
        Delete the entire object in the store
        Args:
        -oid:   The ID of the object in the store
        -delete:    The DeleteRequest object
        Return a DeleteResponse object with may contain a SWORD Error document or nothing at all
        """
        raise NotImplementedError()


class URIManager(object):
    """
    Class for providing a single point of access to all identifiers used by SSS
    """
    def __init__(self, config):
        self.configuration = config

    def atom_id(self, id):
        """ An ID to use for Atom Entries """
        return "tag:container@jper/" + id

    def sd_uri(self):
        return self.configuration.base_url[:-1] + url_for("swordv2_server.service_document")

    def col_uri(self, id):
        """ The url for a collection on the server """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.collection", collection_id=id)

    def edit_uri(self, id):
        """ The Edit-URI """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.entry", entry_id=id)

    def em_uri(self, id):
        """ The EM-URI """
        return self.configuration.base_url[:-1] + url_for("swordv2_server.content", entry_id=id)

    def cont_uri(self, id):
        """ The Cont-URI """
        return self.em_uri(id)

    def state_uri(self, id, type):
        return self.configuration.base_url[:-1] + url_for("swordv2_server.statement", entry_id=id, type=type)

    def agg_uri(self, id):
        return "tag:aggregation@jper/" + id

