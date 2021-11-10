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
    parser.add_argument('command', choices=Commands.all())
    args = parser.parse_args(bddsync_args)
    with open(args.config, 'r', encoding='utf-8') as kwarg_file:
        config = yaml.safe_load(kwarg_file)

    if command == Commands.TEST_REPOSITORY_FOLDERS:
        test_repository_folders_command(command_args, config)
    elif command == Commands.FEATURES:
        features_command(command_args, config)
    elif command == Commands.SCENARIOS:
        scenarios_command(command_args, config)
    elif command == Commands.UPLOAD_FEATURES:
        upload_command(command_args, config)
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


def upload_command(command_args, config):
    parser = argparse.ArgumentParser(f"{NAME} [...] {Commands.UPLOAD_FEATURES}")
    parser.add_argument('feature', nargs='+')
    args = parser.parse_args(command_args)
    paths = args.feature

    feature_paths = []
    for path in paths:
        if os.path.isfile(path) and path.endswith('.feature'):
            feature_paths += [path]
        if os.path.isdir(path):
            feature_paths += [f for f in glob.glob(os.path.join(path, '**/*.feature'), recursive=True)]
    feature_paths = [f.replace(os.sep, '/') for f in feature_paths]

    cucumber = CucumberWrapper(config)
    features = []
    for feature_path in feature_paths:
        features += cucumber.get_features(feature_path)

    xray = XrayWrapper(config)
    duplicated_test = []
    for feature in features:

        # check if there are test with the same name
        if issues := xray.get_issues_by_names([x.name for x in feature.scenarios if not x.test_id]):
            print(f"Issues already exists for scenarios in {feature.path}: \n" +
                  ''.join([f"  - {x['key']}: {x['fields']['summary']}\n" for x in issues]))
            exit(1)

        new_scenario_ids = xray.import_feature(feature.path)
        for i, scenario in enumerate(feature.scenarios):
            new_scenario_id = new_scenario_ids[i]
            if not scenario.test_id:
                scenario.test_id = new_scenario_id
                print(f'Created Test: "{scenario.name}" [{scenario.test_id}]')
            elif scenario.test_id == new_scenario_id:
                print(f'Updated Test: "{scenario.name}" [{scenario.test_id}]')
            else:
                duplicated_test.append(scenario)
                print(f'Duplicated Test: "{scenario.name}" [{scenario.test_id}] -> [{new_scenario_id}]')
                continue

            labels = xray.get_labels(new_scenario_id)
            labels_to_remove = [label for label in labels if label not in scenario.tags and '.feature' not in label]
            xray.remove_labels(new_scenario_id, labels_to_remove)

        feature.repair_tags()
        xray.import_feature(feature.path)


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
    # main([Commands.FEATURES, '--features-re-path', 'features/web/**/*.feature'])
    #
    # main([Commands.SCENARIOS, '-h'])
    # main([Commands.SCENARIOS])
    #
    # main([Commands.UPLOAD, '-h'])
    # main([Commands.UPLOAD_FEATURES, r'features\owa\android'])
    # main([Commands.UPLOAD_FEATURES, r'C:\workspaces\bddsync\features\owa\android\camerasWrapperAndroid.feature'])
    main([Commands.UPLOAD_FEATURES, r'C:\workspaces\verisureowatesting\features\iosWrapper\camerasWrapperIos.feature'])