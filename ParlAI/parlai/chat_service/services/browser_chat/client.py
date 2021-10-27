#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

# from http.client import responses
# from http.client import responses
# from pymongo import results

import json
import urllib
import urllib.parse
import jwt
import datetime
import time
import sys

import websocket
import threading
from parlai.core.params import ParlaiParser
from parlai.scripts.interactive_web import WEB_HTML, STYLE_SHEET, FONT_AWESOME
from http.server import BaseHTTPRequestHandler, HTTPServer

# ALSO HERE WE DEAL WITH THE DATABASE
import pymongo
from bson.objectid import ObjectId


# Database shared (needed) variables
# init the database
# this localhost needs to be configured if the database is on another port.
try:
    myclient = pymongo.MongoClient("mongodb://localhost:27017/")
    # also the database name
    mydb = myclient["bb2"]
    USERS_OBJ = mydb['users'] #main collection object
except:
    print("Error: couldn't connect to database!")
    sys.exit()
               


SHARED = {}


def setup_interactive(ws):
    SHARED['ws'] = ws


new_message = None
message_available = threading.Event()


class BrowserHandler(BaseHTTPRequestHandler):
    """
    Handle HTTP requests.
    """


    def _parse_objects_to_json(self, body):
        """
            Mainly used to take inputs in the form of objects to format it into dict

            + Inputs (utf-8 decoded string or bytes):
                - att1=value1&att2=value2&att3=value3
                - b'username=evvv&email=evram%40evram.com&pass=dy%24e%248Uz&bdate=1996-12-31T20%3A20%3A13.000000'

            + Outputs:
                {
                    att1:value1,
                    att2:value2,
                    att3:value3
                }

            NOTE:
            Different interfaces send different format of requests, for instance using `requests` library in python, sends requests in objects,
                while react interface sends them in different manner, so you as a developer, need to comment/uncomment these two modes.
        """


        # For REACT
        return json.loads(body.decode('utf-8'))
        
        # For requests library
        # body = urllib.parse.unquote_plus(body.decode('utf-8'))
        # fields = body.split("&")
        # fields_dict = {}
        # for field in fields:
        #     att, val = field.split("=")               
        #     fields_dict[att] = val

        # print(fields_dict)
        # return fields_dict


            
    def _interactive_running(self, reply_text=None, retrieve_all=False):
        """
            Private (virtually) method used to assign/place messages at the shared websocket.
        """
        
        data = {}
        
        # if reply_text is not None: #send message
            # data['text'] = reply_text.decode('utf-8')

        data['text'] = reply_text['msg']
        data['history'] = reply_text['history']

        #end episode
        if data['text'] == "[DONE]":
            print('[ Closing socket... ]')
            SHARED['ws'].close()
            SHARED['wb'].shutdown()

        # retrieve all chats for a specific user
        if retrieve_all:
            data['text'] = "[FETCH_ALL_DATA]"

        # jsonify
        json_data = json.dumps(data)
        # queue the message
        SHARED['ws'].send(json_data)
    
    def _remove_unsafe(self, msg):
        """
            Removes any tokens produced by the model such as _POTENTIALY_UNSAFE__
        """
        print(msg)
        us = False
        message_striped = ""
        for i,ch in enumerate(msg):
            if ch == "_" and us == False:
                us = True
            elif ch == "_" and msg[i+1] is not None and msg[i+1]=="_" and us==True:
                us = False
            else:
                if not us:
                    message_striped += ch
        return message_striped

    def _restart(self, reset=False):
        for _ in range(2):
            data = {'text':'begin'}
            json_data = json.dumps(data)
            # queue the message
            SHARED['ws'].send(json_data)
            message_available.wait()
            response = new_message
            print(response)
            message_available.clear()
        if reset:
            data = {'text':'[RESET]'}
            json_data = json.dumps(data)
            # queue the message
            SHARED['ws'].send(json_data)
            message_available.wait()
            response = new_message
            print(response)
            message_available.clear()

    def do_HEAD(self):
        """
        Handle HEAD requests.
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html')   
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')
        
        self.end_headers()

    def do_OPTIONS(self):
        """
            Handle OPTIONS requests: health check request that's needed for request/response between react and tornado frameworks.
        """
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')

        self.end_headers()

    def do_POST(self):
        """
        Handle POST request, especially replying to a chat message.
        """
        global START
        if self.path == '/interact':
            # Main request that's being used, that handles messages/chat from users.

            if START:
                START = False
                # jsonify
                self._restart(True)
    
            # fetches the body content of the request
            content_length = int(self.headers['Content-Length'])
            body = self.rfile.read(content_length)
            body = self._parse_objects_to_json(body)
            
            # here we can fetch the current token .. and move on ..
            user_token = self.headers['token']     #(eg. "00h1") str

            # decode the token
            # for later
            private_key = "evram"
            id = None
            try:
                id = jwt.decode(user_token,private_key , algorithms=["HS256"])['id']
            except jwt.ExpiredSignatureError:
                self.send_error(404, explain="TOKEN EXPIRED")
            except Exception as e:
                self.send_error(404, explain="false token")

            # retrieve this user's history
            id = ObjectId(id)    
            history = None
            try:    
                results = USERS_OBJ.find({'_id':id},{'history':1})
                history = results[0]['history']
            except:
                self.send_error(404, explain="couldn't fetch id from the database")
            body['history'] = history
            
            self._interactive_running(reply_text=body, retrieve_all=False)

            # Set header response
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')
            
            self.end_headers()
            # Prepare model's answer
            model_response = {'id': 'Model', 'episode_done': False}


            message_available.wait()
            model_response['text'] = new_message
            if new_message == "Sorry, this world closed. Returning to overworld.":
                self._restart(True)
                model_response['text'] = "Sorry, I didn't get what you mean!"
            
            model_response['text'] = self._remove_unsafe(str(model_response['text']))
            message_available.clear()

            # store this new message in the history.

            # Don't add these
            if new_message == "type begin" \
                or new_message=="Hello and welcome to the Chatbot." \
                or new_message == "Sorry, Internal Server Error." \
                or new_message == 'type begin'\
                or new_message == "Sorry, I didn't get what you mean!":
                pass
            else:
                history.append(body['msg'])
                history.append(model_response['text'])
    
            try:
                USERS_OBJ.update_one({'_id':id},  {"$set": {"history": history }} )
            except:
                self.send_error(404, explain="couldn't update user's history")

            json_str = json.dumps(model_response)
            # Dump it back to the front.
            self.wfile.write(bytes(json_str, 'utf-8'))


        elif self.path == '/reset':
            data = {}
            data['text'] = "[RESET]"
            # jsonify
            json_data = json.dumps(data)
            # queue the message
            SHARED['ws'].send(json_data)

            # RESET user's history
            user_token = self.headers['token']     #(eg. "00h1") str
            private_key = "evram"
            id = None
            try:
                id = jwt.decode(user_token,private_key , algorithms=["HS256"])['id']
            except jwt.ExpiredSignatureError:
                self.send_error(404, explain="TOKEN EXPIRED")
            except Exception as e:
                self.send_error(404, explain="false token")
            id = ObjectId(id)    
            try:
                USERS_OBJ.update_one({'_id':id},  {"$set": {"history": [] }})
            except:
                self.send_error(404, explain="couldn't update user's history")

            
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')
            self.end_headers()

            message_available.wait()
            message_available.clear()
            
            model_response = {'status':True, 'error':None}
            json_str = json.dumps(model_response)
            # Dump it back to the front.
            self.wfile.write(bytes(json_str, 'utf-8'))

        elif self.path == '/logout':
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')
            self.end_headers()
            model_response = {'status':True, 'error':None}
            json_str = json.dumps(model_response)
            # Dump it back to the front.
            self.wfile.write(bytes(json_str, 'utf-8'))
            

        elif self.path == '/chat':
            """
            Retrieves the whole chat context so far.
            """
            status = True
            error = None

            content_length = int(self.headers['Content-Length'])
            '''
                In this body -later- will be the portion of chat to be retrieved
                For now, it's useless
            '''
            # body = self.rfile.read(content_length)
            # body = self._parse_objects_to_json(body)
            
            user_token = self.headers['token']     #(eg. "00h1") str

            # decode the token
            # for later
            private_key = "evram"
            id = None
            try:
                id = jwt.decode(user_token,private_key , algorithms=["HS256"])['id']
            except jwt.ExpiredSignatureError:
                self.send_error(404, explain="TOKEN EXPIRED")
            except Exception as e:
                self.send_error(404, explain="false token")

            # retrieve this user's history
            # history = []
            id = ObjectId(id)
            try:
                results = USERS_OBJ.find({'_id':id},{'history':1})
                history = results[0]['history']
            except:
                self.send_error(404, explain="couldn't fetch from the database")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')
            self.end_headers()

            model_response = {'status':status, 'error':error, 'history': history}
            json_str = json.dumps(model_response)
            # Dump it back to the front.
            self.wfile.write(bytes(json_str, 'utf-8'))

            
        elif self.path == '/signup':
            # Main handler for signup
            '''
                - Fetches request content (baed on content-length)
                - Parses the bytes object into dictionary like object.
                - Creates the new object and insert it to the database
                - Responses with success.
                # TODO: password needs to be hashed!
            '''

            status = True

            try:
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                body_dict = self._parse_objects_to_json(body) 
                body_dict['history'] = []
            except Exception as e:
                response = {'status':status,'error':e}
                json_str = json.dumps(response)
                # Dump it back to the front.
                self.wfile.write(bytes(json_str, 'utf-8'))   
        
            try:
                result = USERS_OBJ.insert_one(body_dict)
                status = True
            except:
                status = False

            if status:
                self.send_response(200)
            else:
                self.send_error(404, explain="Couldn't insert new element to the database!")

            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')
            self.end_headers()
                
            response = {'status':status,'error':None}
            json_str = json.dumps(response)
            # Dump it back to the front.
            self.wfile.write(bytes(json_str, 'utf-8'))   
        

        elif self.path == '/login':
            #Main handler for login requests
            """
                - Fetches request content (baed on content-length)
                - Parses the bytes object into dictionary like object.
                - Try/except retrieving the username and password.
                - Tokenize the id of the user.
                - Responds with user's information.
            """
            status = True
            error = None

            try:
                content_length = int(self.headers['Content-Length'])
                body = self.rfile.read(content_length)
                body_dict = self._parse_objects_to_json(body)

            except Exception as e:
                self.send_error(404, explain="Couldn't fetch the data, probably Content-Length is not correct.")
                return
                
            # Verify password and email
            # TODO: password needs to be hashed!
            try:
                results = USERS_OBJ.find({"email":body_dict['email'], "pass":body_dict["pass"]})
            except:
                self.send_error(404, explain="Couldn't retrieve from the database, check connections!")
                return

            # this is not an error, this is a zero retrieval request.
            try:
                len(results[0]) 
            except:
                status = False
                error = "No users found."

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS, PATCH, PUT')
            self.end_headers()

            response = {'status':status,'error':error}

            if status:
                response['email'] = results[0]['email']
                # response['bdate'] = results[0]['bdate']
                id = results[0]['_id']
                id = str(id)
                #TODO: read the private key from config.yml
                private_key = "evram"
                # Payload to be tokenized
                payload = {"id":id}
                d = datetime.datetime.utcnow() +  datetime.timedelta(hours=6)
                exp_time = int(time.mktime(d.timetuple()))
                encoded = jwt.encode( payload, private_key, algorithm="HS256", headers={"exp":exp_time})
                response['token'] = encoded
            
            json_str = json.dumps(response)
            self.wfile.write(bytes(json_str, 'utf-8'))  
            
            
        else:
            return self._respond({'status': 500})

    def do_GET(self):
        """
        Respond to GET request, especially the initial load.
        """
        paths = {
            '/': {'status': 200},
            '/favicon.ico': {'status': 202},  # Need for chrome
        }
        if self.path in paths:
            self._respond(paths[self.path])
        else:
            self._respond({'status': 500})

    def _handle_http(self, status_code, path, text=None):
        self.send_response(status_code)
        self.send_response(status_code)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        content = WEB_HTML.format(STYLE_SHEET, FONT_AWESOME)
        return bytes(content, 'UTF-8')

    def _respond(self, opts):
        response = self._handle_http(opts['status'], self.path)
        self.wfile.write(response)

        

def on_message(ws, message):
    """
    Prints the incoming message from the server.

    :param ws: a WebSocketApp
    :param message: json with 'text' field to be printed
    """
    incoming_message = json.loads(message)
    # print("client.py: got a message!") #not printed!
    global new_message
    new_message = incoming_message['text']
    message_available.set()


def on_error(ws, error):
    """
    Prints an error, if occurs.

    :param ws: WebSocketApp
    :param error: An error
    """
    print(error)


def on_close(ws):
    """
    Cleanup before closing connection.

    :param ws: WebSocketApp
    """
    # Reset color formatting if necessary
    print("Connection closed")


def _run_browser():
    host = opt.get('host', 'localhost')
    serving_port = opt.get('serving_port', 8080)

    httpd = HTTPServer((host, serving_port), BrowserHandler)

    print('Please connect to the link: http://{}:{}/'.format(host, serving_port))

    SHARED['wb'] = httpd

    httpd.serve_forever()


def on_open(ws):
    """
    Starts a new thread that loops, taking user input and sending it to the websocket.

    :param ws: websocket.WebSocketApp that sends messages to a browser_manager
    """
    threading.Thread(target=_run_browser).start()


def setup_args():
    """
    Set up args, specifically for the port number.

    :return: A parser that parses the port from commandline arguments.
    """
    parser = ParlaiParser(False, False)
    parser_grp = parser.add_argument_group('Browser Chat')
    parser_grp.add_argument(
        '--port', default=35496, type=int, help='Port used by the web socket (run.py)'
    )
    parser_grp.add_argument(
        '--host',
        default='0.0.0.0',
        type=str,
        help='Host from which allow requests, use 0.0.0.0 to allow all IPs',
    )
    parser_grp.add_argument(
        '--serving_port',
        default=8080,
        type=int,
        help='Port used to configure the server',
    )

    return parser.parse_args()


if __name__ == "__main__":
    START = True
    opt = setup_args()
    port = opt.get('port', 34596)
    print("Connecting to port: ", port)
    ws = websocket.WebSocketApp(
        "ws://0.0.0.0:{}/websocket".format(port),
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.on_open = on_open
    setup_interactive(ws)
    ws.run_forever()
