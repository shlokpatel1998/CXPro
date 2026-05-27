#!/usr/bin/env python3
"""
Tests for the memberships module.
Verifies role constants, permission predicates, and membership helpers.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from contexts.identity_access.memberships import (
    ROLES, ROLE_LABELS, is_valid_role, can_manage_team, can_create_project
)


def test_roles_constant():
    assert ROLES == (
        'OCA',
        'CM',
        'cx_engineer',
        'field_technician',
        'design_engineer',
        'owner_fm'
    )
    assert len(ROLES) == 6


def test_role_labels():
    assert len(ROLE_LABELS) == 6
    assert ROLE_LABELS['OCA'] == "Owner's Commissioning Agent"
    assert ROLE_LABELS['CM'] == 'Construction Manager'
    assert ROLE_LABELS['cx_engineer'] == 'Commissioning Engineer'
    assert ROLE_LABELS['field_technician'] == 'Field Technician'
    assert ROLE_LABELS['design_engineer'] == 'Design Engineer'
    assert ROLE_LABELS['owner_fm'] == 'Owner/Facility Manager'
    for role in ROLES:
        assert role in ROLE_LABELS


def test_is_valid_role_with_valid_values():
    assert is_valid_role('OCA') is True
    assert is_valid_role('CM') is True
    assert is_valid_role('cx_engineer') is True
    assert is_valid_role('field_technician') is True
    assert is_valid_role('design_engineer') is True
    assert is_valid_role('owner_fm') is True


def test_is_valid_role_with_invalid_values():
    assert is_valid_role('') is False
    assert is_valid_role(None) is False
    assert is_valid_role('ADMIN') is False
    assert is_valid_role('admin') is False
    assert is_valid_role('USER') is False
    assert is_valid_role('invalid') is False
    assert is_valid_role('oca') is False
    assert is_valid_role('Oca') is False
    assert is_valid_role('cm') is False
    assert is_valid_role('CX_ENGINEER') is False
    assert is_valid_role(123) is False
    assert is_valid_role([]) is False
    assert is_valid_role({}) is False


def test_all_roles_in_labels():
    for role in ROLES:
        assert role in ROLE_LABELS, f"Role {role} missing from ROLE_LABELS"


def test_can_manage_team_with_valid_roles():
    assert can_manage_team('OCA') is True
    assert can_manage_team('CM') is True
    assert can_manage_team('cx_engineer') is False
    assert can_manage_team('field_technician') is False
    assert can_manage_team('design_engineer') is False
    assert can_manage_team('owner_fm') is False


def test_can_manage_team_with_invalid_values():
    assert can_manage_team(None) is False
    assert can_manage_team('') is False
    assert can_manage_team('ADMIN') is False
    assert can_manage_team('admin') is False
    assert can_manage_team('USER') is False
    assert can_manage_team('invalid') is False
    assert can_manage_team('unknown') is False
    assert can_manage_team('oca') is False
    assert can_manage_team('Oca') is False
    assert can_manage_team('cm') is False
    assert can_manage_team('Cm') is False
    assert can_manage_team(123) is False
    assert can_manage_team([]) is False
    assert can_manage_team({}) is False
    assert can_manage_team(['OCA']) is False


def test_can_create_project_with_valid_roles():
    assert can_create_project('OCA') is True
    assert can_create_project('CM') is True
    assert can_create_project('cx_engineer') is False
    assert can_create_project('field_technician') is False
    assert can_create_project('design_engineer') is False
    assert can_create_project('owner_fm') is False


def test_can_create_project_with_invalid_values():
    assert can_create_project(None) is False
    assert can_create_project('') is False
    assert can_create_project('ADMIN') is False
    assert can_create_project('admin') is False
    assert can_create_project('USER') is False
    assert can_create_project('invalid') is False
    assert can_create_project('unknown') is False
    assert can_create_project('oca') is False
    assert can_create_project('Oca') is False
    assert can_create_project('cm') is False
    assert can_create_project('Cm') is False
    assert can_create_project(123) is False
    assert can_create_project([]) is False
    assert can_create_project({}) is False
    assert can_create_project(['OCA']) is False


def test_all_roles_covered_in_can_manage_team():
    results = {role: can_manage_team(role) for role in ROLES}
    assert results['OCA'] is True
    assert results['CM'] is True
    assert results['cx_engineer'] is False
    assert results['field_technician'] is False
    assert results['design_engineer'] is False
    assert results['owner_fm'] is False


def test_all_roles_covered_in_can_create_project():
    results = {role: can_create_project(role) for role in ROLES}
    assert results['OCA'] is True
    assert results['CM'] is True
    assert results['cx_engineer'] is False
    assert results['field_technician'] is False
    assert results['design_engineer'] is False
    assert results['owner_fm'] is False


def test_both_predicates_are_consistent():
    for role in ROLES:
        assert can_manage_team(role) == can_create_project(role), \
            f"Predicates differ for role {role}"
    invalid_values = [None, '', 'ADMIN', 'invalid', 123, [], {}]
    for value in invalid_values:
        assert can_manage_team(value) == can_create_project(value), \
            f"Predicates differ for value {value}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
