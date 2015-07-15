# CURL commands for interacting with the SWORDv2 Service

If you want to try out the various operations against the SWORDv2 endpoint, the following commands can be used.

Note that in each case a user name and password/api_key are provided, but these will be specific to your setup.  The ones
included below are examples only.

## Get the service document

curl -i http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/service-document

# Send a package for validation

curl -i --data-binary "@service/tests/resources/example.zip" -H "Content-Disposition: filename=example.zip" -H "Content-Type: application/zip" -H "Packaging: http://router.jisc.ac.uk/packages/FilesAndJATS" http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/collection/validate

# Send a package as a notification

curl -i --data-binary "@service/tests/resources/example.zip" -H "Content-Disposition: filename=example.zip" -H "Content-Type: application/zip" -H "Packaging: http://router.jisc.ac.uk/packages/FilesAndJATS" http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/collection/notify

# Retrieve back the Deposit Receipt for the last deposit

(note that the ID of the entry when you do this will be different)

curl -i http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/entry/b581851855c7414eaef4d7fd3f49ed50

# Conneg for the statement via the Edit-IRI

curl -i -H "Accept: application/atom+xml;type=feed" http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/entry/b581851855c7414eaef4d7fd3f49ed50

curl -i -H "Accept: application/rdf+xml" http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/entry/b581851855c7414eaef4d7fd3f49ed50

# Get the statement directly 

curl -i http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/entry/b581851855c7414eaef4d7fd3f49ed50/statement/atom

curl -i http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/entry/b581851855c7414eaef4d7fd3f49ed50/statement/rdf

# Obtain the original deposit

curl -i http://admin:468a75c9-01fb-4f92-a8b1-3f0d10ed1492@localhost:5025/entry/b581851855c7414eaef4d7fd3f49ed50/content