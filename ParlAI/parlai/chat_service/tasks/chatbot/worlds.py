#!/usr/bin/env python3

# Copyright (c) Facebook, Inc. and its affiliates.
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
#
# py parlai/chat_service/tasks/overworld_demo/run.py --debug --verbose

from parlai.core.worlds import World
from parlai.chat_service.services.messenger.worlds import OnboardWorld
from parlai.core.agents import create_agent_from_shared


# ---------- Chatbot demo ---------- #
class MessengerBotChatOnboardWorld(OnboardWorld):
    """
    Example messenger onboarding world for Chatbot Model.
    """

    @staticmethod
    def generate_world(opt, agents):
        return MessengerBotChatOnboardWorld(opt=opt, agent=agents[0])

    def parley(self):
        self.episodeDone = True


class MessengerBotChatTaskWorld(World):
    """
    Example one person world that talks to a provided agent (bot).
    """

    MAX_AGENTS = 1
    MODEL_KEY = 'blender_90M'

    def __init__(self, opt, agent, bot):
        self.agent = agent
        self.episodeDone = False
        self.model = bot
        self.first_time = True
        

    @staticmethod
    def generate_world(opt, agents):
        if opt['models'] is None:
            raise RuntimeError("Model must be specified")
        return MessengerBotChatTaskWorld(
            opt,
            agents[0],
            create_agent_from_shared(
                opt['shared_bot_params'][MessengerBotChatTaskWorld.MODEL_KEY]
            ),
        )

    @staticmethod
    def assign_roles(agents):
        agents[0].disp_id = 'ChatbotAgent'

    def parley(self):
        # print (f"Parley function got here!") #this runs infinitely
        if self.first_time:
            self.agent.observe(
                {
                    'id': 'World',
                    'text': 'Hello and welcome to the Chatbot.',
                }
            )
            # Here we need to load the history of the user
            self.first_time = False
        # user token finally got here.
        a = self.agent.act()
        
        if a is not None:
            a['text']=a['text'].replace("\n"," ").replace(".  ",", ").replace("  ",", ")
            if '[DONE]' in a['text']:
                self.episodeDone = True
            elif '[RESET]' in a['text']:
                self.model.reset()
                self.agent.observe({"text": "[History Cleared]", "episode_done": False})
            elif '[FETCH_ALL_DATA]' in a['text']:
                # here we need to return back the history.
                pass
            else:
                print("===act====")
                print(a)
                print("~~~~~~~~~~~")
                if a['history'] is not None:
                    # print('history_strings')
                    # print(self.model.history_strings )
                    # print("history.historystring")
                    # print(self.model.history.history_strings )
                    
                    # self.model.history_strings = a['history']
                    self.model.history.reset()                
                    # self.model.history.history_strings = a['history']
                    for h in a['history']:
                        self.model.history._update_strings(h)
                        self.model.history._update_raw_strings(h)
                        self.model.history._update_vecs(h)
                        
                self.model.observe(a)
                # print("====history====")
                # print(self.model.history.history_strings)
                # print("~~~~~~~~~~~")
                response = self.model.act()
                response['text']=response['text'].replace("\n"," ").replace(".  ",", ").replace("  ",", ")
                print("===response====")
                print(response)
                print("~~~~~~~~~~~")
                self.agent.observe(response)

    def episode_done(self):
        return self.episodeDone

    def shutdown(self):
        self.agent.shutdown()


# ---------- Overworld -------- #
class MessengerOverworld(World):
    """
    World to handle moving agents to their proper places.
    """

    def __init__(self, opt, agent):
        self.agent = agent
        self.opt = opt
        self.first_time = True
        self.episodeDone = False

    @staticmethod
    def generate_world(opt, agents):
        return MessengerOverworld(opt, agents[0])

    @staticmethod
    def assign_roles(agents):
        for a in agents:
            a.disp_id = 'Agent'

    def episode_done(self):
        return self.episodeDone

    def parley(self):
        if self.first_time:
            self.agent.observe(
                {
                    'id': 'Overworld',
                    'text': "type begin",
                    'quick_replies': ['begin', 'exit'],
                }
            )
            self.first_time = False
        
        a = self.agent.act()
        if a is not None and a['text'].lower() == 'exit':
            self.episode_done = True
            return 'EXIT'
        if a is not None and a['text'].lower() == 'begin':
            self.episodeDone = True
            return 'default'
        elif a is not None:
            self.agent.observe(
                {
                    'id': 'Overworld',
                    'text': 'Invalid option. Please type "begin".',
                    'quick_replies': ['begin'],
                }
            )
