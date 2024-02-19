from fastapi import HTTPException, Request
from starlette.types import Message

def is_authenticated(request: Request):
    user = request.session.get('userdata')
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

def structure_files(file_dict, file_id):
    file_data = file_dict[file_id]
    is_root = file_data['parents'][0]['isRoot'] if 'parents' in file_data else False

    content = [structure_files(file_dict, child_id) for child_id in file_dict if file_dict[child_id].get('parents', []) and file_dict[child_id].get('parents', [])[0].get('id', '') == file_id]
    result = {
            'title': file_data['title'],
            'id': file_data['id'],
            'file_type': 'directory' if content else 'file',
    }
    if content:
        result.update({'content': content})
    if not is_root and file_data['parents']:
        parent_id = file_data['parents'][0].get('id', '')
        result.update({'parent': parent_id})
    return result