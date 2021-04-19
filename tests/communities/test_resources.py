# -*- coding: utf-8 -*-
#
# This file is part of Invenio.
# Copyright (C) 2020 CERN.
#
# Invenio is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

"""Community module tests."""

import copy
import json

import pytest
from flask import url_for

from invenio_communities.communities.records.api import Community

import time
# def assert_error_resp(res, expected_errors, expected_status_code=400):
#     """Assert errors in a client response."""
#     assert res.status_code == expected_status_code
#     payload = res.json
#     errors = payload.get('errors', [])
#     for field, msg in expected_errors:
#         if not field:  # top-level "message" error
#             assert msg in payload['message'].lower()
#             continue
#         assert any(
#             e['field'] == field and msg in e['message'].lower()
#             for e in errors), payload


# def create_test_community(client, user, data):
#     """Create test community."""
#     login_user_via_session(client, user=user)
#     list_url = url_for('invenio_records_rest.comid_list')
#     resp = client.post(list_url, json=data)
#     assert resp.status_code == 201
#     return resp


# def logout_user_session(client):
#     """Logout a user from the Flask test client session."""
#     with client.session_transaction() as sess:
#         del sess['user_id']


def _assert_single_item_response(response):
    """Assert the fields present on a single item response."""
    response_fields = response.json.keys()
    fields_to_check = [
        'created', 'id', 'links', 'metadata', 'updated'
    ]

    for field in fields_to_check:
        assert field in response_fields


def _assert_optional_items_response(response):
    """Assert the fields present on the metadata and access"""
    metadata_fields = response.json['metadata'].keys()
    fields_to_check = [
        "description", "curation_policy", "page", "website", 
        "funding", "affiliations"
    ]

    access_fields = response.json['access'].keys()
    fields_to_check = [
       "member_policy", "record_policy"
    ]
    # TODO: Add when general vocabularies are ready
    # domains
    for field in fields_to_check:
        assert field in access_fields


def _assert_single_item_search(response):
    """Assert the fields present on the search response """
    response_fields = response.json.keys()
    fields_to_check = [
        "aggregations", "hits", "links", "sortBy"
    ]

    for field in fields_to_check:
        assert field in response_fields


def test_simple_flow(
    app, client_with_login, location, minimal_community_record, headers,
    es_clear
):
    """Test a simple REST API flow."""
    client = client_with_login
    # Create a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record))
    assert res.status_code == 201
    _assert_single_item_response(res)

    created_community = res.json
    id_ = created_community["id"]

    # Read the community
    res = client.get(f'/communities/{id_}', headers=headers)
    assert res.status_code == 200
    assert res.json['metadata'] == \
        created_community['metadata']

    read_community = res.json

    Community.index.refresh()

    # Search for created commmunity
    res = client.get(
        f'/communities', query_string={'q': f'id:{id_}'}, headers=headers)
    assert res.status_code == 200
    assert res.json['hits']['total'] == 1
    assert res.json['hits']['hits'][0]['metadata'] == \
        created_community['metadata']

    # Update community
    data = copy.deepcopy(read_community)
    data["metadata"]["title"] = 'New title'
    res = client.put(
        f'/communities/{id_}', headers=headers, data=json.dumps(data))
    assert res.status_code == 200
    assert res.json['metadata']["title"] == 'New title'

    updated_community = res.json

    Community.index.refresh()

    # Search for updated commmunity
    res = client.get(
        f'/communities', query_string={'q': f'id:{id_}'}, headers=headers)
    assert res.status_code == 200
    assert res.json['hits']['total'] == 1
    assert res.json['hits']['hits'][0]['metadata'] == \
        updated_community['metadata']
    data = res.json['hits']['hits'][0]
    assert updated_community['metadata']['title'] == 'New title'

    # Delete community
    res = client.delete(f'/communities/{id_}', headers=headers)
    assert res.status_code == 204

    # Read again community, should return 404
    res = client.get(f'/communities/{id_}', headers=headers)
    assert res.status_code == 410
    assert res.json["message"] == "The record has been deleted."


def test_post_schema_validation(
    app, client_with_login, location, minimal_community_record, headers, es_clear
):

    """Test the validity of community json schema"""
    client = client_with_login

    #Creta a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record)        
    )
    assert res.status_code == 201
    _assert_single_item_response(res)
    created_community = res.json
    id_ = created_community['id'] 

    res = client.get(f'/communities/{id_}', headers=headers)
    assert res.status_code == 200
    metadata_ = created_community['metadata']
    access_ = created_community['access']

    # Assert required fields
    assert 'title' in metadata_
    assert 'type' in metadata_
    assert 'visibility' in access_

    # Assert required enums
    assert metadata_['type'] in ['organization', 'event', 'topic', 'project',]
    assert access_['visibility'] in ['public', 'private', 'hidden']
    

def test_post_metadata_schema_validation(
    app, client_with_login, location, minimal_community_record, headers, 
    es_clear
):
    """Test the validity of community metadata schema"""
    client = client_with_login

    # Alter paypload for each field for test
    data = copy.deepcopy(minimal_community_record)
    
    # Assert field size constraints  (id, title, description, curation policy, page)
    # ID max 100
    data["id"] = "".join([str(i) for i in range(101)]),
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(data)        
    )
    assert res.status_code == 400
    assert res.json["message"] == "A validation error occurred." 
    assert res.json["errors"][0]['field'] == 'id' 
    assert res.json["errors"][0]['messages'] == ['Not a valid string.']

    # Title max 250
    data["id"] = "my_comm"
    data['metadata']['title'] = "".join([str(i) for i in range(251)])
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(data)        
    )
    assert res.status_code == 400
    assert res.json["message"] == "A validation error occurred."    
    assert res.json["errors"][0]['field'] == 'metadata.title' 
    #assert res.json["errors"][0]['messages'] == ['Title is too long.']   

    # Description max 2000
    data['metadata']['title'] = "New Title"
    data['metadata']['description'] = "".join([str(i) for i in range(2001)])
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(data)        
    )
    assert res.status_code == 400
    assert res.json["message"] == "A validation error occurred."    
    assert res.json["errors"][0]['field'] == 'metadata.description' 
    #assert res.json["errors"][0]['messages'] == ['Description is too long.']

    # Curation policy max 2000
    data['metadata']['description'] = "basic description"
    data['metadata']['curation_policy'] = "".join([str(i) for i in range(2001)])
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(data)        
    )
    assert res.status_code == 400
    assert res.json["message"] == "A validation error occurred."    
    assert res.json["errors"][0]['field'] == 'metadata.curation_policy' 
    #assert res.json["errors"][0]['messages'] == ['Curation policy is too long.']

    # Curation policy max 2000
    data['metadata']['curation_policy'] = "no policy"
    data['metadata']['page'] = "".join([str(i) for i in range(2001)])
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(data)        
    )
    assert res.status_code == 400
    assert res.json["message"] == "A validation error occurred."    
    assert res.json["errors"][0]['field'] == 'metadata.page' 
    #assert res.json["errors"][0]['messages'] == ['Page is too long.']


    data['metadata']['page'] = "basic page"
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(data))        
    assert res.status_code == 201
    _assert_single_item_response(res)
    # # TODO: create bigger json payload as text fixture including all
    # # TODO: test for empty string
    # # _assert_optional_items_metadata(response)
    

def test_post_community_with_existing_id(
    app, client_with_login, location, minimal_community_record, headers,
    es_clear
):
    """Test create two communities with the same id"""
    client = client_with_login
    
    #Creta a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record)        
    )
    assert res.status_code == 201
    _assert_single_item_response(res)
    created_community = res.json
    id_ = created_community['id']

    #Creta another community with the same id
    minimal_community_record['id'] = id_  
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record)        
    )
    assert res.status_code == 400
    assert res.json['message'] == f'Community {id_} already exists.'


def test_post_community_with_deleted_id(
    app, client_with_login, minimal_community_record, headers,
    es_clear
):
    """Test create a community with a deleted id"""
    client = client_with_login
    
    #Creta a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record))
    assert res.status_code == 201
    _assert_single_item_response(res)
    created_community = res.json
    id_ = created_community['id']

    # Delete community
    res = client.delete(f'/communities/{id_}', headers=headers)
    assert res.status_code == 204

    #Creta another community with the same id
    minimal_community_record['id'] = id_  
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record))
    assert res.status_code == 201
    _assert_single_item_response(res)
    

def test_post_self_links(
    app, client_with_login, minimal_community_record, headers,
    es_clear
): 
    """Test self links generated after post"""
    client = client_with_login
    
    #Creta a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record))
    assert res.status_code == 201
    _assert_single_item_response(res)
    created_community = res.json
    id_ = created_community['id']
    # assert '/'.join(created_community['links']['self'].split('/')[-2:]) == f'communities/{id_}'
    assert created_community['links']['self'] == f'https://127.0.0.1:5000/api/communities/{id_}'
    assert created_community['links']['self_html'] == f'https://127.0.0.1:5000/ui/communities/{id_}'


def test_simple_search_response(
    app, client_with_login, minimal_community_record, headers,
    es_clear
):
    """Test get/list and search functionality"""
    client = client_with_login
    # Create a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record))
    assert res.status_code == 201

    created_community = res.json
    id_ = created_community["id"]

    # Search for any commmunity
    res = client.get(
        f'/communities', query_string={'q': f''}, headers=headers)
    assert res.status_code == 200
    _assert_single_item_search(res)

    assert res.json['hits']['total'] == 1
    assert res.json['hits']['hits'][0]['metadata'] == \
         created_community['metadata']
    
    # Create another community
    data = copy.deepcopy(minimal_community_record)
    data['id'] = "comm_id2"
    data['metadata']['title'] = 'new title'
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(data))
    assert res.status_code == 201

    id2_ = res.json["id"]

    # Search filter for the second commmunity
    res = client.get(
        f'/communities', query_string={'q':'new'}, headers=headers)
    assert res.status_code == 200
    _assert_single_item_search(res)
    assert res.json['hits']['total'] == 1
    assert res.json['hits']['hits'][0]['id'] == id2_

    # Sort results by oldest
    res = client.get(
    f'/communities', query_string={'q':'', 'sort':'oldest'}, headers=headers)
    assert res.status_code == 200
    assert res.json['hits']['hits'][0]['id'] == id_
    
    # Test for page and size
    res = client.get(
    f'/communities', query_string={'q':'', 'size':'5', 'page':'2'}, headers=headers)
    assert res.status_code == 200
    assert res.json['hits']['total'] == 2


def test_simple_get_response(
    app, client_with_login, headers, es_clear
):
    """Test get response json schema"""
    client = client_with_login

    big_community_record = \
    {
    "access": {
        "visibility": "public",
        "member_policy": "open",
        "record_policy": "open",
    },
    "id": "my_community_id",
    "metadata": {
        "title": "My Community",
        "description": "This is an example Community.",
        "type": "event",
        "curation_policy": "This is the kind of records we accept.",
        "page": "Information for my community.",
        "website": "https://inveniosoftware.org/",
        "funding":[{
            "funder": {
                "name": "European Commission",
                "identifier": "00k4n6c32",
                "scheme": "ror"
            },
            "award": {
                "title": "OpenAIRE",
                "number": "246686",
                "identifier": ".../246686",
                "scheme": "openaire"
            }
        }],
       "affiliations": [{
            "name": "CERN",
            "identifiers": [
                {
                "identifier": "01ggx4157",
                "scheme": "ror"
                }
            ]
       }]
    }
    }

    # Create a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(big_community_record))
    assert res.status_code == 201
    _assert_single_item_response(res)
    id_ = res.json["id"]

    # Read the community
    res = client.get(f'/communities/{id_}', headers=headers)
    assert res.status_code == 200
    _assert_optional_items_response(res)

    # Read a non-existed community
    res = client.get(f'/communities/{id_[:-1]}', headers=headers)
    assert res.status_code == 404
    assert res.message == 'The persistent identifier does not exist.'


def test_simple_put_response(
    app, client_with_login, minimal_community_record, headers,
    es_clear
):
    """Test put response basic functionality"""
    client = client_with_login
    # Create a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record))
    assert res.status_code == 201
    _assert_single_item_response(res)
    created_community = res.json
    id_ = created_community['id']

    data = copy.deepcopy(minimal_community_record)
    data["metadata"] = \
    {
        "title": "New Community",
        "description": "This is an example Community.",
        "type": "event",
        "curation_policy": "This is the kind of records we accept.",
        "page": "Information for my community.",
        "website": "https://inveniosoftware.org/",  
    }
    test_simple_put_response
    res = client.put(
        f'/communities/{id_}', headers=headers, data=json.dumps(data))
    assert res.status_code == 200
    assert res.json['id'] == id_
    assert res.json['metadata'] == data["metadata"]
    assert res.json["revision_id"] == int(created_community["revision_id"])+1

    # Update non-existing community
    res = client.put(
        f'/communities/{id_[:-1]}', headers=headers, data=json.dumps(data))
    assert res.status_code == 404
    assert res.json['message'] == 'The persistent identifier does not exist.'


def test_simple_delete_response(
    app, client_with_login, minimal_community_record, headers,
    es_clear
):
    """Test delete and request deleted community """
    client = client_with_login
    
    #Creta a community
    res = client.post(
        '/communities', headers=headers,
        data=json.dumps(minimal_community_record))
    assert res.status_code == 201
    _assert_single_item_response(res)
    created_community = res.json
    id_ = created_community['id']

    # Delete community
    res = client.delete(f'/communities/{id_}', headers=headers)
    assert res.status_code == 204

    # Read the community
    res = client.get(f'/communities/{id_}', headers=headers)
    assert res.status_code == 410
    assert res.json['message']  == 'The record has been deleted.'

    # Delete non-existing community
    res = client.delete(f'/communities/{id_[:-1]}', headers=headers)
    assert res.status_code == 404
    assert res.json['message']  == 'The persistent identifier does not exist.'