import json

import requests


class Folder:

    def __init__(self, path: str, folder_id: str):
        self.path = path
        self.id = folder_id

    def __str__(self):
        return f'{self.path} [{self.id}]'


class XrayWrapper:

    def __init__(self, config):
        self.base_url = config['xray']['url']
        self.auth = config['test_repository_user'], config['test_repository_pass']
        self.project_key = config['test_project_id']

        for field in config['xray']['fields']:
            if field['name'] == 'test_repository_path':
                self.TEST_REPOSITORY_PATH_FIELD = field['key']
            if field['name'] == 'test_plans':
                self.TEST_PLANS_FIELD = field['key']

    def get_test_repository_folders(self, path='/') -> list[Folder]:
        response = requests.get(f'{self.base_url}/rest/raven/1.0/api/testrepository/'
                                f'{self.project_key}/folders/-1', auth=self.auth)
        response_json = response.text
        if not response_json:
            return []

        response_dict = json.loads(response_json)

        def add_folders(all_folders: list, current_folder):
            for sub_folder in current_folder['folders']:
                all_folders.append(Folder(f"{sub_folder['testRepositoryPath']}/{sub_folder['name']}/",
                                          sub_folder['id']))
                add_folders(all_folders, sub_folder)

        add_folders(folders := [], response_dict)
        return folders if path == '/' else [folder for folder in folders if folder.path.startswith(path)]

    def import_feature(self, feature):
        try:
            response = requests.post(f'{self.base_url}/rest/raven/1.0/import/feature',
                                     params={'projectKey': self.project_key},
                                     files={'file': open(feature.path, 'r', encoding='utf-8')},
                                     auth=self.auth)
            try:
                imported_scenarios = response.json()
            except json.decoder.JSONDecodeError:
                raise Exception(f'Not a JSON response. Response:\n{response.text}')
            if not len(imported_scenarios) == len(feature.scenarios):
                raise Exception(f'Some scenarios were not imported. Response:\n{response.text}')
            return [x['key'] for x in imported_scenarios]

        except Exception as e:
            raise Exception(f'ERROR: Cannot import "{feature.path}" due to error: {e}')

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
                                 json={"jql": jql, "maxResults": 1000, "fields": ['summary']},
                                 auth=self.auth)
        if response.status_code != 200:
            raise Exception(f'ERROR: Cannot get search due to error: '
                            f'(status code: {response.status_code}) {response.text}')

        return response.json()['issues']

    def get_issue(self, issue_key: str, fields: list[str]) -> dict:
        response = requests.get(f"{self.base_url}/rest/api/2/issue/{issue_key}?fields={','.join(fields)}",
                                auth=self.auth)
        if response.status_code != 200:
            raise Exception(f'ERROR: Cannot get labels due to error: '
                            f'(status code: {response.status_code}) {response.text}')
        return response.json()

    def remove_labels(self, issue_key: str, labels: list):
        response = requests.put(f'{self.base_url}/rest/api/2/issue/{issue_key}',
                                json={"update": {"labels": [{"remove": label} for label in labels]}},
                                auth=self.auth)
        if response.status_code != 204:
            raise Exception(f'ERROR: Cannot remove labels {labels} due to error: '
                            f'(status code: {response.status_code}) {response.text}')

    def add_tests_to_test_plans(self, issue_keys: list[str], test_plan_keys: list[str]):
        for test_plan_key in test_plan_keys:
            print(f'Add {issue_keys} to test plan: [{test_plan_key}]')
            response = requests.post(
                f'{self.base_url}/rest/raven/1.0/api/testplan/{test_plan_key}/test',
                json={"add": issue_keys},
                auth=self.auth)
            if response.status_code != 200:
                raise Exception(f'ERROR: Cannot add {issue_keys} to test plan: [{test_plan_key}]')

    def remove_tests_from_test_plans(self, issue_keys: list[str], test_plan_keys: list[str]):
        for test_plan_key in test_plan_keys:
            print(f'Remove {issue_keys} from test plan: [{test_plan_key}]')
            response = requests.post(
                f'{self.base_url}/rest/raven/1.0/api/testplan/{test_plan_key}/test',
                json={"remove": issue_keys},
                auth=self.auth)
            if response.status_code != 200:
                raise Exception(f'ERROR: Cannot add {issue_keys} to test plan: [{test_plan_key}]')

    def move_test_dir(self, issue_key: str, test_dir: str):
        print(f'[{issue_key}] move to directory: {test_dir}')
        response = requests.put(
            f'{self.base_url}/rest/api/2/issue/{issue_key}',
            json={"fields": {self.TEST_REPOSITORY_PATH_FIELD: test_dir}},
            auth=self.auth)
        if response.status_code != 204:
            raise Exception(f'ERROR: Cannot move [{issue_key}] to folder "{test_dir}" due to error: {response.text}')

    def make_dirs(self, path: str):
        folders = self.get_test_repository_folders()

        folder_path = '/'
        parent_folder_id = '-1'

        def _get_folder(_folder_path, _folders):
            for _folder in _folders:
                if _folder_path == _folder.path:
                    return _folder

        path_tokens = path.lstrip('/').split('/')
        for path_token in path_tokens:
            folder_path += path_token + '/'
            if folder := _get_folder(folder_path, folders):
                parent_folder_id = folder.id
            else:
                response = requests.post(
                    f'{self.base_url}/rest/raven/1.0/api/testrepository/{self.project_key}/folders/{parent_folder_id}',
                    json={"name": path_token},
                    auth=self.auth)
                if response.status_code != 200:
                    raise Exception(f'ERROR: Cannot create folder "{folder_path}"')
                parent_folder_id = response.json()['id']


if __name__ == '__main__':
    import yaml
    with open('../bddfile.yml', 'r', encoding='utf-8') as kwarg_file:
        xray = XrayWrapper(yaml.safe_load(kwarg_file))
    # print(xray.get_test_repository_folders())
    xray.make_dirs('/Test/A/B')
