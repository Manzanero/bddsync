# bddsync

Tools to synchronize BDD files with test management tools like Jira-Xray

## Setting Up

Place a file named `bddfile.yml` in project root directory. Following this example: 

``` yaml
version: <bddfile_version (default=1)>
features: <features_root_folder (default=features/)>
result: <result_file_path (default=output/result.json)>
code_repository_type: <code_repository_type (default=behave)>
test_repository_type: <code_repository_type (default=xray)>
test_project_id: <test_project_id (required)>
test_plans:
  - tag: <tracked_test_plan_tag_1>
    id: <tracked_test_plan_id_1>
  - tag: <tracked_test_plan_tag_2>
    id: <tracked_test_plan_id_2>
    ...
test_sets:
  - tag: <tracked_test_sets_tag_1>
    id: <tracked_test_sets_id_1>
  - tag: <tracked_test_sets_tag_2>
    id: <tracked_test_sets_id_2>
    ...

xray:
  url: <jira_base_url (required, example=https://jira.xxx.com)>
  fields:
    - name: test_repository_path <jira_url (required)>
      key: <test_repository_path_field (required, example=customfield_123456)>
      type: str
    - name: test_plans
      key: <test_plans_field (required, example=customfield_654321)>
      type: list[str]

```

In each use, bddsync ask for credentials. To avoid this behaviour, set the environment variables 
`TEST_REPOSITORY_USER` y `TEST_REPOSITORY_PASS`

## Usage

Start with `bddsync` (with optional arguments) followed by the command:

```
$ bddsync [-h] [--config CONFIG] [-u TEST_REPOSITORY_USER] [-p TEST_REPOSITORY_PASS] COMMAND [-h] [...]

optional arguments:
  -h, --help               show this help message and exit
  --config CONFIG          alternative path to bddsync.yml
  -u TEST_REPOSITORY_USER  if not in environment
  -p TEST_REPOSITORY_PASS
  
commands available:
  test-repository-folders
  features
  scenarios
  upload-features
```

### test-repository-folders

It shows the list of repository folders and the corresponding id:

```
$ bddsync [...] test-repository-folders [-h] [--folder FOLDER]

optional arguments:
  -h, --help       show this help message and exit
  --folder FOLDER  folder to filter, else from root
```

### features

It shows the list of features and the corresponding path:

```
$ bddsync [...] features [-h]

optional arguments:
  -h, --help       show this help message and exit
```

### scenarios

It shows the list of scenarios and the corresponding features:

```
$ bddsync [...] scenarios [-h]

optional arguments:
  -h, --help       show this help message and exit
```

### upload-features

Updates the test repository according to these guidelines:
  - Tags will be repaired and reordered, (1st line for tracked tags, 2nd line for other tags)
  - New scenarios in code will be created them in test repository and receive their ID in code
  - Updated scenarios in code will be updated them in test repository
  - Deleted scenarios in code **won't be deleted** in test repository, the user updates test in repository manually
  - Renamed scenario in code **won't be renamed** in test repository, **the user will be warned and process stops**, the user updates test in repository manually
  - Tracked test plan tag added to a scenario will add the test to test plan
  - Tracked test plan tag removed to a scenario will remove the test from test plan
  - If there are duplicated test names, **the user will be warned and process stops**
  - If scenario were duplicated during process (fixes in progress), **the user will be warned**

Tip: avoid create tests in test repository first, test may be duplicated with this process

```
$ bddsync [...] upload-features [-h] feature [feature ...]

positional arguments:
  feature                can be a glob expression, use * as wildcard 

optional arguments:
  -h, --help  show this help message and exit
```


