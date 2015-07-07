# JPER SWORDv2 Deposit Endpoint

This document describes the SWORDv2 deposit protocol operations supported by JPER.

Section numbers referenced here are as per the SWORDv2 profile here: http://swordapp.github.io/SWORDv2-Profile/SWORDProfile.html

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



## 6.1. Retrieving a Service Document

    Client                   Interaction                 Server
    ------                   -----------                 ------
    
    Request Service    ->    GET SD-IRI      ->         Get Service Document
    Document                 + Auth                     with 2 collections:
                                                         * validate notification
                                                         * create notification
                                                         
    Receive Service    <-    200 (OK)        <-        
    Document                 XML Body


## 6.3.1. Creating a Resource with a Binary File Deposit

    Client                   Interaction                        Server
    ------                   -----------                        ------
    
    Deposit Zip        ->    POST Col-IRI        ->             Accept Deposit
    File                     + Auth                             * store file in file store
                             Packaging: FilesAndJATS            * create primitive notification
                             In-Progress: False                 * send notification to API
                             Content-Type: application/zip      * get response from API
                                                                * replay response via SWORDv2
                                                                
                                                                
    Receive Error      <-   4xx (Error)          <-             In case of error
                            XML Body
                            
    Receive Deposit    <-   201 (Created)        <-             On Success 
    Receipt                 Location: Edit-IRI
                            Deposit Receipt

To retrieve the Deposit Receipt again at a later date

    Client                   Interaction                        Server
    ------                   -----------                        ------
    
    Get Deposit        ->    GET Edit-IRI        ->             Replay request to API
    Receipt                  + Auth                                                             
                                                                
    Receive Error      <-   4xx (Error)          <-             In case of error
                            XML Body
                            
    Item is no longer  <-   404 (Not Found)      <-             In case not found
    in the Router
                            
    Receive Deposit    <-   201 (Created)        <-             On Success 
    Receipt                 Deposit Receipt
    

## 6.4. Retrieving the content

    Client                   Interaction                        Server
    ------                   -----------                        ------
    
    Retrieve Content    ->   GET Cont-IRI           ->          Request notification from API
                             + Auth                             Retrieve content URL from metadata
                             Accept-Packaging:FilesAndJATS                  
    
    Content not         <-   404 (Not Found)        <-          If not found
    available
    
    
    Download file       <-  303 (See Other)         <-          On success
                            Location: download URL

Note that only the original file format will be available - no Atom Feed version will be negotiable

## 6.9. Retrieving the Statement

    Client                   Interaction                        Server
    ------                   -----------                        ------
    
    Request Satement    ->   GET State-IRI          ->          Request notification from API
                                                                Convert to statement format
    
    Item is no longer   <-   404 (Not Found)        <-          In case not found
    in the Router
    
    Receive Statement   <-   200 (OK)               <-          On success
                             XML Body
