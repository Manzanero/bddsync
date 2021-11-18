import argparse
import glob
import os
import shlex
import sys

import yaml

from bddsync import xray_wrapper
from bddsync.cucumber_wrapper import CucumberWrapper
from bddsync.xray_wrapper import XrayWrapper

NAME = 'bddsync'


class Commands:
    TEST_REPOSITORY_FOLDERS = 'test-repository-folders'
    FEATURES = 'features'
    SCENARIOS = 'scenarios'
    UPLOAD_FEATURES = 'upload-features'
    UPLOAD_RESULTS = 'upload-results'

    @classmethod
    def all(cls):
        return [i[1] for i in cls.__dict__.items() if not i[0].startswith('_') and isinstance(i[1], str)]


def main(arg_vars: list = None):
    arg_vars = (shlex.split(arg_vars) if isinstance(arg_vars, str) else arg_vars) if arg_vars else sys.argv[1:]

    bddsync_args = []
    command = None
    command_args = None
    for var in arg_vars:
        bddsync_args.append(var)
        if var in Commands.all():
            command = var
            command_args = arg_vars[arg_vars.index(command) + 1:]
            break
    else:
        bddsync_args = ['-h']

    parser = argparse.ArgumentParser(NAME)
    parser.add_argument('--config', default='bddfile.yml')
    parser.add_argument('-u', '--test-repository-user')
    parser.add_argument('-p', '--test-repository-pass')
    parser.add_argument('command', choices=Commands.all())
    args = parser.parse_args(bddsync_args)

    # config
    with open(args.config, 'r', encoding='utf-8') as kwarg_file:
        config = yaml.safe_load(kwarg_file)

    # credentials
    if args.test_repository_user:
        test_repository_user = args.user
    elif 'TEST_REPOSITORY_USER' in dict(os.environ):
        test_repository_user = os.environ['TEST_REPOSITORY_USER']
    else:
        test_repository_user = input('Enter repository user: ')
    config['test_repository_user'] = test_repository_user

    if args.test_repository_pass:
        test_repository_pass = args.user
    elif 'TEST_REPOSITORY_PASS' in dict(os.environ):
        test_repository_pass = os.environ['TEST_REPOSITORY_PASS']
    else:
        test_repository_pass = input('Enter repository pass: ')
    config['test_repository_pass'] = test_repository_pass

    if command == Commands.TEST_REPOSITORY_FOLDERS:
        test_repository_folders_command(command_args, config)
    elif command == Commands.FEATURES:
        features_command(command_args, config)
    elif command == Commands.SCENARIOS:
        scenarios_command(command_args, config)
    elif command == Commands.UPLOAD_FEATURES:
        upload_features_command(command_args, config)
    else:
        print(f'Error: command "{command}" not managed yet')
        exit(1)


def test_repository_folders_command(command_args, config):
    parser = argparse.ArgumentParser(f"{NAME} [...] {Commands.TEST_REPOSITORY_FOLDERS}")
    parser.add_argument('--folder', help='Choose a folder, else "root"')
    args = parser.parse_args(command_args)

    xray = XrayWrapper(config)
    folders = xray.get_test_repository_folders(args.folder)
    for folder in folders:
        print(folder)


def features_command(command_args, config):
    parser = argparse.ArgumentParser(f"{NAME} [...] {Commands.FEATURES}")
    parser.parse_args(command_args)

    cucumber = CucumberWrapper(config)
    for feature in cucumber.features:
        print(feature.name)


def scenarios_command(command_args, config):
    parser = argparse.ArgumentParser(f"{NAME} [...] {Commands.SCENARIOS}")
    parser.parse_args(command_args)

    cucumber = CucumberWrapper(config)
    for feature in cucumber.features:
        for scenario in feature.scenarios:
            print(scenario.name)


def upload_features_command(command_args, config):
    parser = argparse.ArgumentParser(f"{NAME} [...] {Commands.UPLOAD_FEATURES}")
    parser.add_argument('feature', nargs='+')
    args = parser.parse_args(command_args)
    paths = args.feature

    cucumber = CucumberWrapper(config)

    feature_paths = []
    for path in paths:
        feature_paths += [f.replace(os.sep, '/') for f in glob.glob(path, recursive=True) if f.endswith('.feature')]

    features = []
    for feature_path in feature_paths:
        features += cucumber.get_features(feature_path)

    if not features:
        print('No Feature found')

    xray = XrayWrapper(config)
    for feature in features:
        print(f'Processing feature: {feature.name} (path="{feature.path}")')

        # check if there are test with the same name
        if issues := xray.get_issues_by_names([x.name for x in feature.scenarios]):
            summaries = [issue['fields']['summary'] for issue in issues]
            duplicates = []

            for issue in issues:
                if summaries.count(issue['fields']['summary']) > 1:
                    duplicates.append(issue)

            if duplicates:
                print(f'Some issues are duplicated for scenarios in "{feature.path}": \n' +
                      ''.join([f"  - {issue['key']}: {issue['fields']['summary']}\n" for issue in duplicates]))
                exit(1)

        new_scenario_ids = xray.import_feature(feature)
        for i, scenario in enumerate(feature.scenarios):
            new_scenario_id = new_scenario_ids[i]
            if not scenario.test_id:
                scenario.test_id = new_scenario_id
                print(f'Created Test: "{scenario.name}" [{scenario.test_id}]')
            elif scenario.test_id == new_scenario_id:
                print(f'Updated Test: "{scenario.name}" [{scenario.test_id}]')
            else:
                if int(scenario.test_id.split('-')[1]) > int(new_scenario_id.split('-')[1]):
                    hint = 'check if this key is the correct key'
                else:
                    hint = 'check if this key has to be removed'
                print(f'Duplicated Test: "{scenario.name}" [{scenario.test_id}] -> {hint}: [{new_scenario_id}]')
                continue

            issues = xray.get_issue(new_scenario_id,
                                    ['labels', 'status', xray.TEST_REPOSITORY_PATH_FIELD, xray.TEST_PLANS_FIELD])

            # manage labels
            labels = issues['fields']['labels']
            labels_to_remove = [label for label in labels if label not in scenario.tags]
            xray.remove_labels(new_scenario_id, labels_to_remove)

            # manage path
            test_dir = issues['fields'][xray.TEST_REPOSITORY_PATH_FIELD]
            if scenario.test_dir and scenario.test_dir != test_dir:
                xray.make_dirs(scenario.test_dir)
                xray.move_test_dir(new_scenario_id, scenario.test_dir)

            # manage plans
            xray_test_plans = issues['fields'][xray.TEST_PLANS_FIELD]
            code_test_plans = [plan.id for plan in scenario.test_plans]
            code_test_plans_to_add = [plan for plan in code_test_plans if plan not in xray_test_plans]
            xray_test_plans_to_remove = [plan for plan in xray_test_plans if plan not in code_test_plans]
            xray.add_tests_to_test_plans([new_scenario_id], code_test_plans_to_add)
            xray.remove_tests_from_test_plans([new_scenario_id], xray_test_plans_to_remove)

        print('Repairing feature tags')
        feature.repair_tags()
        print('Validating result')
        xray.import_feature(feature)
        print(f'Feature updated successfully: {feature.name}')


if __name__ == '__main__':
    # main(['-h'])
    # main(['-h', Commands.TEST_REPOSITORY_FOLDERS])
    # main(['-h', '--config', 'bddfile.yml', Commands.TEST_REPOSITORY_FOLDERS])
    # main(['-h', '--config', 'bddfile.yml', Commands.TEST_REPOSITORY_FOLDERS, '-h'])
    # main(['-h', '--config', 'bddfile.yml', Commands.TEST_REPOSITORY_FOLDERS, '-h', '--folder', '/OWA'])
    #
    # main([Commands.TEST_REPOSITORY_FOLDERS, '-h'])
    # main([Commands.TEST_REPOSITORY_FOLDERS])
    # main([Commands.TEST_REPOSITORY_FOLDERS, '-h', '--folder', '/OWA'])
    #
    # main([Commands.FEATURES, '-h'])
    # main([Commands.FEATURES])
    # main([Commands.FEATURES, '--features-re-path', 'features/Web/**/*.feature'])
    #
    # main([Commands.SCENARIOS, '-h'])
    # main([Commands.SCENARIOS])
    #
    # main([Commands.UPLOAD, '-h'])
    # main([Commands.UPLOAD_FEATURES, r'features\Verisure OWA\Wrapper Android'])
    main([Commands.UPLOAD_FEATURES, r'C:\workspaces\bddsync\features\Verisure OWA\Wrapper IOS\routineWrapperIos.feature'])
