import json
import time

import requests


class Folder:

    def __init__(self, path: str, folder_id: str):
        self.path = path
        self.id = folder_id

    def __str__(self):
        return f'{self.path} [{self.id}]'


class XrayWrapper:

    def __init__(self, config):
        self.base_url = config['url']
        self.auth = config['test_repository_user'], config['test_repository_pass']
        self.project_key = config['test_project']

        self.test_repository_path_field = config['fields']['test_repository_path']
        self.test_plans_field = config['fields']['test_plans']
        self.execution_test_plans_field = config['fields']['execution_test_plans']
        self.execution_test_environments_field = config['fields']['execution_test_environments']
        self.execution_fix_versions_field = config['fields']['execution_fix_versions']

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
            response = requests.post(
                f'{self.base_url}/rest/raven/1.0/import/feature',
                params={'projectKey': self.project_key},
                files={'file': open(feature.path, 'r', encoding='utf-8')},
                auth=self.auth
            )
            try:
                imported_scenarios = response.json()
                tests = [x for x in imported_scenarios if x["issueType"]["name"] == "Test"]
            except json.decoder.JSONDecodeError:
                raise Exception(f'Not a JSON response. Response:\n{response.text}')
            if not len(tests) == len(feature.scenarios):
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
        response = requests.post(
            f'{self.base_url}/rest/api/2/search',
            json={"jql": jql, "maxResults": 1000, "fields": ['summary']},
            auth=self.auth
        )
        if response.status_code != 200:
            raise Exception(f'ERROR: Cannot get search due to error: '
                            f'(status code: {response.status_code}) {response.text}')

        try:
            return response.json()['issues']
        except json.decoder.JSONDecodeError:
            raise Exception(f'Not a JSON response. Response:\n{response.text}') from None

    def get_issue(self, issue_key: str, fields: list[str]) -> dict:
        response = requests.get(
            f"{self.base_url}/rest/api/2/issue/{issue_key}?fields={','.join(fields)}",
            auth=self.auth
        )
        if response.status_code != 200:
            raise Exception(f'ERROR: Cannot get labels from [{issue_key}] due to error: '
                            f'(status code: {response.status_code}) {response.text}')
        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            raise Exception(f'Not a JSON response. Response:\n{response.text}') from None

    def rename_issue(self, issue_key: str, summary: str) -> dict:
        response = requests.put(
            f"{self.base_url}/rest/api/2/issue/{issue_key}",
            json={"fields": {"summary": summary}},
            auth=self.auth
        )
        if response.status_code != 200:
            raise Exception(f'ERROR: Cannot rename [{issue_key}] due to error: '
                            f'(status code: {response.status_code}) {response.text}')
        try:
            return response.json()
        except json.decoder.JSONDecodeError:
            raise Exception(f'Not a JSON response. Response:\n{response.text}') from None

    def remove_labels(self, issue_key: str, labels: list):
        response = requests.put(
            f'{self.base_url}/rest/api/2/issue/{issue_key}',
            json={"update": {"labels": [{"remove": label} for label in labels]}},
            auth=self.auth
        )
        if response.status_code != 204:
            raise Exception(f'ERROR: Cannot remove labels {labels} from [{issue_key}] due to error: '
                            f'(status code: {response.status_code}) {response.text}')

    def add_tests_to_test_plans(self, issue_keys: list[str], test_plan_keys: list[str]):
        for test_plan_key in test_plan_keys:
            print(f'Add {issue_keys} to test plan: [{test_plan_key}]')
            response = requests.post(
                f'{self.base_url}/rest/raven/1.0/api/testplan/{test_plan_key}/test',
                json={"add": issue_keys},
                auth=self.auth
            )
            if response.status_code != 200:
                raise Exception(f'ERROR: Cannot add {issue_keys} to test plan: [{test_plan_key}]')

    def remove_tests_from_test_plans(self, issue_keys: list[str], test_plan_keys: list[str]):
        for test_plan_key in test_plan_keys:
            print(f'Remove {issue_keys} from test plan: [{test_plan_key}]')
            response = requests.post(
                f'{self.base_url}/rest/raven/1.0/api/testplan/{test_plan_key}/test',
                json={"remove": issue_keys},
                auth=self.auth
            )
            if response.status_code != 200:
                raise Exception(f'ERROR: Cannot add {issue_keys} to test plan: [{test_plan_key}]')

    def move_test_dir(self, issue_key: str, test_dir: str):
        print(f'[{issue_key}] move to directory: {test_dir}')
        response = requests.put(
            f'{self.base_url}/rest/api/2/issue/{issue_key}',
            json={"fields": {self.test_repository_path_field: test_dir}},
            auth=self.auth
        )
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
                    auth=self.auth
                )
                if response.status_code != 200:
                    raise Exception(f'ERROR: Cannot create folder "{folder_path}"')
                parent_folder_id = response.json()['id']

    def import_result(self, result_path: str, summary: str = None, test_environments: list[str] = None,
                      fix_versions: list[str] = None, test_plan_keys: list[str] = None, labels: list[str] = None):
        summary = summary or f"Imported test execution {int(time.time())}"
        info = {"fields": {"project": {"key": self.project_key}, "summary": summary}}
        if test_plan_keys:
            info['fields'][self.execution_test_plans_field] = test_plan_keys  # noqa
        if test_environments:
            info['fields'][self.execution_test_environments_field] = test_environments  # noqa
        if fix_versions:
            info['fields'][self.execution_fix_versions_field] = [{"name": fix_version} for fix_version in fix_versions]  # noqa
        if labels:
            info['fields']['labels'] = labels  # noqa

        response = requests.post(
            f'{self.base_url}/rest/raven/1.0/import/execution/cucumber/multipart',
            files={'result': open(result_path, 'rb'), 'info': json.dumps(info)},
            auth=self.auth
        )
        if response.status_code != 200:
            raise Exception(f'Cannot import result due to error: '
                            f'(status code: {response.status_code}) {response.text}')
        try:
            test_execution = response.json()['testExecIssue']
            return test_execution
        except KeyError:
            raise Exception(f'Not a test execution issue in response. Response:\n{response.text}')
        except json.decoder.JSONDecodeError:
            raise Exception(f'Not a JSON response. Response:\n{response.text}') from None


# if __name__ == '__main__':
#     import yaml
#     import os
#     with open('../bddfile.yml', 'r', encoding='utf-8') as kwarg_file:
#         config = yaml.safe_load(kwarg_file)
#         config['test_repository_user'] = os.environ['TEST_REPOSITORY_USER']
#         config['test_repository_pass'] = os.environ['TEST_REPOSITORY_PASS']
#         # XrayWrapper(config).make_dirs('/Test/A/B')
#         # print(XrayWrapper(config).get_test_repository_folders())
#         # XrayWrapper(config).import_result(
#         #     '../output/result.json',
#         #     test_environments=['INT'],
#         #     fix_versions=['RW21_23'],
#         #     test_plan_keys=['DCH-6689'],
#         #     labels=['a']
#         # )
