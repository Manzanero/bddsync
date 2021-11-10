import json
import re

import requests


class XrayWrapper:

    def __init__(self, config):
        self.base_url = config['xray']['url']
        self.auth = config['xray']['user'], config['xray']['pass']
        self.project_key = config['test_project_id']

    def get_test_repository_folders(self, folder=None):
        folder = folder or 'root'
        response = requests.get(f'{self.base_url}/rest/raven/1.0/api/testrepository/'
                                f'{self.project_key}/folders/-1', auth=self.auth)
        response_json = response.text
        if not response_json:
            return []

        response_dict = json.loads(response_json)

        def add_folders(all_folders: list, current_folder):
            for sub_folder in current_folder['folders']:
                all_folders.append(f"{sub_folder['testRepositoryPath']}/{sub_folder['name']}")
                add_folders(all_folders, sub_folder)

        add_folders(folders := [], response_dict)
        return [f for f in folders if re.findall(f'{folder}/', f) or f == folder] if folder != 'root' else folders

    def import_feature(self, path):
        try:
            response = requests.post(f'{self.base_url}/rest/raven/1.0/import/feature',
                                     params={'projectKey': self.project_key},
                                     files={'file': open(path, 'r', encoding='utf-8')},
                                     auth=self.auth)
            imported_scenarios = response.json()
            return [x['key'] for x in imported_scenarios]

        except Exception as e:
            raise Exception(f'ERROR: Cannot import "{path}" due to error: {e}')

    def get_issues_by_names(self, names: list) -> list:
        if not names:
            return []

        def _replaces(s: str):
            for c in '[]':
                s = s.replace(c, '')
            return s

        summary_conditions = 'or '.join([f"summary ~ '{_replaces(x)}' " for x in names])
        jql = f'project = {self.project_key} and ' + summary_conditions
        response = requests.post(f'{self.base_url}/rest/api/2/search',
                                 json={"jql": jql, "fields": ['summary']},
                                 auth=self.auth)
        if response.status_code != 200:
            raise Exception(f'ERROR: Cannot get search due to error: '
                            f'(status code: {response.status_code}) {response.text}')

        return response.json()['issues']

    def get_labels(self, issue_key: str) -> list:
        response = requests.get(f'{self.base_url}/rest/api/2/issue/{issue_key}?fields=labels', auth=self.auth)
        if response.status_code != 200:
            raise Exception(f'ERROR: Cannot get labels due to error: (status code: {response.status_code}) {response.text}')
        return response.json()['fields']['labels']

    def remove_labels(self, issue_key: str, labels: list):
        response = requests.put(f'{self.base_url}/rest/api/2/issue/{issue_key}',
                                json={"update": {"labels": [{"remove": label} for label in labels]}},
                                auth=self.auth)
        if response.status_code != 204:
            raise Exception(f'ERROR: Cannot remove labels {labels} due to error: '
                            f'(status code: {response.status_code}) {response.text}')

