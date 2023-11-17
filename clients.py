
from stat import filemode
from datetime import datetime
import requests
import json
import logging as log
import os

log_folder = "logs/"
if not os.path.exists(log_folder):
    os.mkdir(log_folder)

saves_folder = "saves/"
if not os.path.exists(saves_folder):
    os.mkdir(saves_folder)

log.basicConfig(filename=log_folder + "trace.log", level=log.INFO, 
        datefmt='%d-%m-%Y %H:%M:%S',
        format="%(asctime)s %(levelname)s %(message)s")

class Barcher(object):
    """
    A simple client library for the Clash of Clans API in python
    """
    def __init__(self, token):
        import requests
        self.requests = requests
        self.token = token
        self.api_endpoint = "https://api.clashofclans.com/v1"
        self.timeout = 30

    """
    Generic get method to the API
    """
    def get(self, uri, params=None):
        headers = {
            'Accept': "application/json",
            'Authorization': "Bearer " + self.token,
            'charset': 'utf-8'
        }

        url = self.api_endpoint + uri

        try:
            response = self.requests.get(url, params=params, headers=headers, timeout=30)
            return response.json()
        except:
            if 400 <= response.status_code <= 599:
                return "Error {}".format(response.status_code)
    """
    Search for clans with specific criteria
    params: {
      "name": 'SomeClanName',
      "warFrequency": ['always', 'moreThanOncePerWeek','oncePerWeek','lessThenOncePerWeek','never','Unknown'],
      "locationId": 1,
      "minMembers": 20,
      "minClanPoints": 1200,
      "minClanLevel": 1-10,
      "limit": 5,
      "after": 2,
      "before": 100
    }
    """
    def search_clans(self,params):
        return self.get('/clans', params)

    """
    Find a specific clan by clan tag (omit # symbol)
    ex: #123456 would be
    client.find_clan("123456")
    """
    def find_clan(self, tag):
        return self.get('/clans/%23' + tag)

    """
    Retrieve member for a specific clan tag
    client.clan_members_for("123456")
    """
    def clan_members_for(self, tag):
        return self.get('/clans/%23' + tag + '/members')
    """
    return all locations for clash players
    client.locations()
    """
    def locations(self):
        return self.get('/locations')

    """
    return specific location by its id
    client.location(4)
    """
    def location(self,id):
        return self.get('/locations/' + id)

    """
    return all rankings associated with a given location:
    client.rankings_at_location(1, 5)
    """
    def rankings_at_location(self, location_id, ranking_id):
        return self.get('/locations/' + location_id + '/rankings/' + ranking_id)

    """
    return all leagues
    client.leagues()
    """
    def leagues(self):
        return self.get('/leagues')


class Member:
    def __init__(self, tag, name):
        self.tag = tag
        self.name = name
    
    def __repr__(self):
        return "M({}, {})".format(self.tag, self.name)

    def to_notion_properties(self):
        notion_properties = {
            "Name": {
                "title": [
                    {
                        "text": {
                            "content": self.name
                        }
                    }
                ]
            },
            "id": {
                "rich_text": [
                    {
                        "text": {
                            "content": self.tag
                        }
                    }
                ]
            },
        }
        return notion_properties

class NotionClient:
    def __init__(self, notion_token, db_id):
        self.notion_token = notion_token
        self.db_id = db_id
        self.headers = {
            "Authorization": "Bearer " + notion_token,
            "Notion-Version": "2021-08-16",
            "Content-Type": "application/json; charset=utf-8"
        }
    
    def read_database(self):
        db_url = "https://api.notion.com/v1/databases/" + self.db_id + "/query"
        res = requests.request("POST", db_url, headers=self.headers)
        return json.loads(res.text)
    
    def save_database(self):
        database = self.read_database()
        with open("database.json", "w") as file:
            json.dump(database, file, indent=4)
    
    def remove_page(self, page_id):
        block_url = "https://api.notion.com/v1/blocks/" + page_id
        requests.request("DELETE", block_url, headers=self.headers)

    def add_member(self, member):
        page_url = "https://api.notion.com/v1/pages"

        new_page_data = {
            "parent": { "database_id": self.db_id },
            "properties": member.to_notion_properties()            
        }
        data = json.dumps(new_page_data)
        requests.request("POST", page_url, headers=self.headers, data=data)


class CocClient:
    def __init__(self, coc_token, clan_id):
        self.coc_token = coc_token
        self.clan_id = clan_id

    def get_members(self):
        client = Barcher(self.coc_token)
        clan = client.find_clan(self.clan_id)
        if "memberList" in clan:
            members = []
            for member in clan["memberList"]:
                members.append(Member(
                    member["tag"], 
                    member["name"]
                ))
            return members
        else:
            log.warn("Members list is empty")
            return []
    

class Updater:
    def __init__(self, configs, mode):
        if mode == "prod":
            db_id = configs["notion_db_prod"]
        elif mode == "test":
            db_id = configs["notion_db_test"]
        else:
            db_id = ""
        self.notion_client = NotionClient(configs["notion_token"], db_id)
        self.coc_client = CocClient(configs["coc_token"], configs["clant_id"])
    

    def member_exists(self, member_list, tag_member):
        for member in member_list:
            if tag_member == member.tag:
                return True
        return False

    def get_members_to_add(self, database, member_list):
        members_to_add = []
        for member in member_list:
            id_present = False
            for page in database["results"]:
                rich_text_value = page["properties"]["id"]["rich_text"]
                if rich_text_value:
                    id_page_member = rich_text_value[0]["text"]["content"]
                else:
                    id_page_member = None
                if id_page_member == member.tag:
                    id_present = True
            if not id_present:
                members_to_add.append(member)
        return members_to_add

    def add_all_new_members(self, database, member_list):
        members_to_add = self.get_members_to_add(database, member_list)
        for member in members_to_add:
            log.info("🟢 {}".format(member.name))
            self.notion_client.add_member(member)

    def get_pages_to_remove(self, database, member_list):
        pages_to_remove = []
        for page in database["results"]:
            rich_text_value = page["properties"]["id"]["rich_text"]
            if rich_text_value:
                id_page_member = rich_text_value[0]["text"]["content"]
                if not self.member_exists(member_list, id_page_member):
                    pages_to_remove.append(page)
        return pages_to_remove

    def remove_all_old_pages(self, database, member_list):
        pages_to_remove = self.get_pages_to_remove(database, member_list)
        for page in pages_to_remove:
            member_name = page["properties"]["Name"]["title"][0]["text"]["content"]
            log.info("🔴 {}".format(member_name))
            self.notion_client.remove_page(page["id"])

    def save_database(self, database):
        members = []
        for member in database["results"]:
            members.append({
                "name": member["properties"]["Name"]["title"][0]["plain_text"],
                "tags": [tag["name"] for tag in member["properties"]["Tags"]["multi_select"]],
                "JDC": member["properties"]["JDC"]["select"]["name"] if member["properties"]["JDC"]["select"] else ""
            })
        today = datetime.now().strftime("%d-%m-%Y %H:%M")
        with open(saves_folder + today + ".json", "w", encoding='utf8') as file:
            file.write(json.dumps(members, ensure_ascii=False))

    def notion_update(self):
        database = self.notion_client.read_database()
        member_list = self.coc_client.get_members()

        if member_list:
            self.save_database(database)
            self.remove_all_old_pages(database, member_list)
            self.add_all_new_members(database, member_list)

