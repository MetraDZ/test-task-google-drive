import uvicorn
import secrets
import logging
from fastapi import BackgroundTasks, FastAPI, Request, Depends, Response, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from pydrive.auth import GoogleAuth, AuthenticationError, AuthenticationRejected
from pydrive.drive import GoogleDrive
from pydrive.files import ApiRequestError
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import RedirectResponse, HTMLResponse

from functions import is_authenticated, structure_files

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=secrets.token_urlsafe(16))
logging.basicConfig(filename='info.log', level=logging.DEBUG)
gauth = GoogleAuth()
drive = GoogleDrive()

def log_info(req_body, res_body):
    logging.info(req_body)
    logging.info(res_body)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    '''
        Logging Middleware, which logs every action made on server
            -request: Request | Latest request, made to the server
            -call_next | Api call to be made after
    '''
    req_body = await request.body()
    response = await call_next(request)
    
    res_body = b''
    async for chunk in response.body_iterator:
        res_body += chunk
    
    task = BackgroundTasks().add_task(log_info, req_body, res_body)
    return Response(content=res_body, status_code=response.status_code, 
        headers=dict(response.headers), media_type=response.media_type, background=task)

@app.get('/')
def public(request: Request):
    '''
        Home endpoint, which returns HTML page
    '''
    with open('index.html', 'r') as html_file:
        return HTMLResponse(html_file.read())

@app.get('/user')
def user(request: Request):
    '''
        Endpoint, which is called to retrieve user data from current session
        If info is not found, Google OAuth url is returned
    '''
    user = request.session.get('userdata')
    if user:
        return JSONResponse({'user_data': user})
    auth_url = gauth.GetAuthUrl()
    return JSONResponse({'auth': auth_url}, status_code=401)

@app.get('/auth')
async def auth(request: Request):
    '''
        Endpoint for Google OAuth callback.
        Accepts OAuth code for Google Drive usage.
    '''
    try:
        code = dict(request.query_params).get('code')
        gauth.Auth(code)
        drive.auth = gauth
        userdata = gauth.credentials.id_token
    except (AuthenticationError, AuthenticationRejected):
        return RedirectResponse(url='/')
    request.session['userdata'] = dict(userdata)
    return RedirectResponse(url='/')

@app.post('/logout', dependencies=[Depends(is_authenticated)])
async def logout(request: Request):
    '''
        Simple logout endpoint, which cleans session
        Session is also cleaned on app restart
    '''
    request.session.pop('userdata', None)
    return JSONResponse({})

@app.get('/list_files', dependencies=[Depends(is_authenticated)])
async def list_files(request: Request):
    '''
        Endpoint, which lists all user files, except for ones in trash
        Returns JSONs of every user file
    '''
    files_list = drive.ListFile({'q': 'trashed=false', 'maxResults': 100}).GetList()
    files_dict = {file['id']:file for file in files_list}
    response = []
    for file_id in files_dict:
        parents = files_dict[file_id].get('parents', [])
        if parents and parents[0].get('isRoot', False):
            response.append(structure_files(files_dict, file_id))
    return JSONResponse({"files": response})
        
@app.post('/upload_file', dependencies=[Depends(is_authenticated)])
async def upload_file(request: Request, file: UploadFile):
    '''
        Endpoint, which upload file to Google Drive
            -file: UploadFile | File in BytesIO representation
    '''
    try:
        uploaded_file = drive.CreateFile({'title': file.filename,'mimeType': file.content_type})
        uploaded_file.content = file.file
        uploaded_file.Upload()
    except ApiRequestError:
        raise HTTPException(detail='This file cannot be uploaded', status_code=400)
    return JSONResponse({'detail': 'File uploaded'})

@app.delete('/delete_file', dependencies=[Depends(is_authenticated)])
async def delete_file(request: Request, file_id: str):
    '''
        Endpoint, which delete file from Google Drive
            -file_id: str | Google file id e.g. 1ZG-6UvUV1aL_5UwTBRVe8Wn66cW_hPAS
    '''
    try:
        file = drive.CreateFile({'id': file_id})
        file.Delete()
    except ApiRequestError:
        raise HTTPException(detail='No such file', status_code=400)
    return JSONResponse({'detail': 'File deleted'})

@app.put('/move_file', dependencies=[Depends(is_authenticated)])
async def move_file(request: Request, file_id: str, folder_id: str):
    '''
        Endpoint, which moves file to specific directory
            -file_id: str | Google file id
            -folder_id: str | Google directory id
    '''
    try:
        file = drive.CreateFile({'id': file_id})
        file.Upload()
        file['parents'] = [{"kind": "drive#parentReference", "id": folder_id, "isRoot": False}]
        file.Upload()   
    except ApiRequestError:
        raise HTTPException(detail='Either file_id or folder_id is wrong', status_code=400)
    return JSONResponse({'detail': 'File moved'})

@app.put('/edit_file', dependencies=[Depends(is_authenticated)])
async def edit_file(request: Request, file_id: str, new_content: str):
    '''
        Endpoint, which edits file, if possible
            file_id: str | Google file id
            new_content: str | Content, which file contents will be overwritten with
    '''
    try:
        file = drive.CreateFile({'id': file_id})
        file.SetContentString(new_content)
        file.Upload()
    except ApiRequestError:
        raise HTTPException(detail='Not editable file type or no such file', status_code=400)
    return JSONResponse({'detail': 'File edited'})

if __name__ == '__main__':
    uvicorn.run(app, port=8000)