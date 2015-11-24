# JPER SWORDv2 Deposit Endpoint

This application provides a thin interface between the JPER notification API and a publisher's SWORDv2 deposit 
client, allowing the publisher to interact with JPER via SWORDv2 rather than its native API.

For information to help users get connected to this deposit endpoint see the 
[User Guide]((https://github.com/JiscPER/jper-sword-in/blob/develop/docs/system/USER.md))

## SWORDv2 protocol operations

This interface implements a sub-set of the full range of SWORDv2 protocol operations

Section numbers referenced here are as per the [SWORDv2 profile](http://swordapp.github.io/SWORDv2-Profile/SWORDProfile.html)

The following operations ARE supported:

* 6.1. Retrieving a Service Document
* 6.3.1. Creating a Resource with a Binary File Deposit
* 6.4. Retrieving the content
* 6.9. Retrieving the Statement

All other operations are unsupported at this time.

The URL's provided by the service map to the SWORDv2 definitions as follows:

* SD-IRI - the URL for retrieving the service document for JPER
* Col-IRI - the "collection" URLs, of which there are precisely 2: one for validation deposits and the other for creating notifications
* Edit-IRI - the URL for the created notification
* Cont-IRI - The URL for retrieving any zip file deposited with the notification metadata
* EM-IRI - identical to Cont-IRI in this case
* State-IRI - the URL for retrieving a "statement" about the notification

The following sections detail the behaviour of this application at each of those protocol operations

### 6.1. Retrieving a Service Document

![ServiceDocument](https://raw.githubusercontent.com/JiscPER/jper-sword-in/develop/docs/system/ServiceDocument.png)


### 6.3.1. Creating a Resource with a Binary File Deposit

![CreateBinary](https://raw.githubusercontent.com/JiscPER/jper-sword-in/develop/docs/system/CreateBinary.png)

To retrieve the Deposit Receipt again at a later date

![DepositReceipt](https://raw.githubusercontent.com/JiscPER/jper-sword-in/develop/docs/system/DepositReceipt.png)
    

### 6.4. Retrieving the content

![RetrieveContent](https://raw.githubusercontent.com/JiscPER/jper-sword-in/develop/docs/system/RetrieveContent.png)

Note that only the original file format will be available - no Atom Feed version will be negotiable

### 6.9. Retrieving the Statement

![Statement](https://raw.githubusercontent.com/JiscPER/jper-sword-in/develop/docs/system/Statement.png)