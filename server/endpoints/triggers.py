from flask import request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt_claims

from server.returncodes import *
from server.security import permissions_accepted_for_resources, ResourcePermissions
import server.messaging


def send_data_to_trigger():
    from server.context import running_context

    @jwt_required
    @permissions_accepted_for_resources(ResourcePermissions('playbooks', ['execute']))
    def __func():
        data = request.get_json()
        workflows_in = set(data['execution_uids'])
        data_in = data['data_in']
        arguments = data['arguments'] if 'arguments' in data else []

        workflows_awaiting_data = set(running_context.controller.get_waiting_workflows())
        uids = set.intersection(workflows_in, workflows_awaiting_data)
        user_id = get_jwt_identity()
        authorization_not_required, authorized_uids = get_authorized_uids(
            uids, user_id, get_jwt_claims().get('roles', []))
        add_user_in_progress(authorized_uids, user_id)
        uids = list(authorized_uids | authorization_not_required)
        running_context.controller.send_data_to_trigger(data_in, uids, arguments)
        return list(uids), SUCCESS

    return __func()


def get_authorized_uids(uids, user_id, role_ids):
    authorized_uids = set()
    authorization_not_required = set()
    for uid in uids:
        if not server.messaging.workflow_authorization_cache.workflow_requires_authorization(uid):
            authorization_not_required.add(uid)
        elif any(server.messaging.workflow_authorization_cache.is_authorized(uid, user_id, role_id)
                 for role_id in role_ids):
            authorized_uids.add(uid)
    return authorization_not_required, authorized_uids


def add_user_in_progress(uids, user_id):
    for uid in uids:
        server.messaging.workflow_authorization_cache.add_user_in_progress(uid, user_id)
