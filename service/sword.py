from sss.core import SwordServer, ServiceDocument, SDCollection
from flask import url_for

class JperSword(SwordServer):

    def __init__(self, config, auth):
        SwordServer.__init__(self, config, auth)

        # create a URIManager for us to use
        self.um = URIManager(self.configuration)

    ##############################################
    ## Methods required by the JPER integration

    def container_exists(self, path):
        raise NotImplementedError()

    def media_resource_exists(self, path):
        raise NotImplementedError()

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
        -collection:    the ID of the collection to be deposited into
        -deposit:       the DepositRequest object to be processed
        Returns a DepositResponse object which will contain the Deposit Receipt or a SWORD Error
        """
        raise NotImplementedError()

    def get_media_resource(self, path, accept_parameters):
        """
        Get a representation of the media resource for the given id as represented by the specified content type
        -id:    The ID of the object in the store
        -content_type   A ContentType object describing the type of the object to be retrieved
        """
        raise NotImplementedError()

    def get_container(self, path, accept_parameters):
        """
        Get a representation of the container in the requested content type
        Args:
        -oid:   The ID of the object in the store
        -content_type   A ContentType object describing the required format
        Returns a representation of the container in the appropriate format
        """
        raise NotImplementedError()

    def get_statement(self, path, type=None):
        raise NotImplementedError()


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

