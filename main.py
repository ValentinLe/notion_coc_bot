
import sys
import json
from clients import Updater
from coc import Coc

def read_confs():
    with open("conf.json", "r") as file:
        return json.load(file)

def get_coc_token(configs):
    client = Coc(configs["coc_username"], configs["coc_password"])
    keys = client.getAllkeys()
    for key in keys["keys"]:
        client.deleteKey(key["id"])
    return client.createKey()["key"]["key"]


def main():
    configs = read_confs()
    if len(sys.argv) == 2:
        mode = sys.argv[1]

        # set key for coc api
        configs["coc_token"] = get_coc_token(configs)
        
        # update notion
        updater = Updater(configs, mode)
        updater.notion_update()


if __name__ == "__main__":
    main()
