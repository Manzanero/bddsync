import glob
import os
import re

STEP_KEYWORDS = ['given', 'when', 'then', 'and', 'but']


class TestPlan:

    def __init__(self, tag, test_plan_id):
        self.tag = tag
        self.id = test_plan_id


class TestSet:

    def __init__(self, tag, test_set_id):
        self.tag = tag
        self.id = test_set_id


class Scenario:

    def __init__(self, cucumber, feature, line, name, outline, tags, body):
        self.cucumber: CucumberWrapper = cucumber
        self.feature: Feature = feature
        self.line: str = line
        self.name: str = name
        self.outline: bool = outline
        self.tags: list[str] = tags
        self.body: str = body

        self.test_id = None
        self.test_plans: list[TestPlan] = []
        self.test_sets: list[TestSet] = []
        self.effective_tags = tags + feature.tags

        self._find_test_id()
        self._find_test_plans()
        self._find_test_sets()

    def __str__(self):
        return f'Scenario (name="{self.name}")'

    def _find_test_id(self):
        if self.cucumber.config['test_repository'] == 'xray':
            for tag in self.tags:
                match = re.findall(r'^\w+-\d+$', tag)
                if match and \
                        match not in [x.id for x in self.cucumber.test_plans] and \
                        match not in [x.id for x in self.cucumber.test_sets]:
                    self.test_id = match[0]
                    return

    def _find_test_plans(self):
        if not self.cucumber.config.get('test_plans'):
            return

        if self.cucumber.config['test_repository'] == 'xray':
            for test_plan in self.cucumber.test_plans:
                if test_plan.tag in self.effective_tags:
                    self.test_plans.append(test_plan)

    def _find_test_sets(self):
        if not self.cucumber.config.get('test_sets'):
            return

        if self.cucumber.config['test_repository'] == 'xray':
            for test_set in self.cucumber.test_sets:
                if test_set.tag in self.effective_tags:
                    self.test_sets.append(test_set)

    @property
    def _tags_block(self):
        if self.cucumber.config['test_repository'] == 'xray':
            tags = set(self.tags)
            tags_line1 = ['@automated']
            tags.discard('automated')
            if self.test_id:
                tags_line1.append('@' + self.test_id)
                tags.discard(self.test_id)
            for test_plan in self.test_plans:
                if test_plan.tag not in self.feature.tags:
                    tags_line1.append('@' + test_plan.tag)
                tags.discard(test_plan.tag)
            for test_set in self.test_sets:
                if test_set.tag not in self.feature.tags:
                    tags_line1.append('@' + test_set.tag)
                tags.discard(test_set.tag)
            tags_line2 = ['@' + tag for tag in sorted(tags)]
            return '  ' + ' '.join(tags_line1) + '\n  ' + ' '.join(tags_line2) + '\n'

    @property
    def _name_block(self):
        return ('  Scenario Outline: ' if self.outline else '  Scenario: ') + self.name + '\n'

    @property
    def _body_block(self):
        return '\n'.join(self.body) + '\n'

    @property
    def text(self):
        return self._tags_block + self._name_block + self._body_block

    @property
    def test_dir(self):
        features_root = self.cucumber.config['features'].replace('\\', '/').strip('/')
        return '/' + self.feature.path.split(features_root + '/')[1].replace(".feature", "")


class Feature:

    def __init__(self, cucumber, path, line: int, name: str, tags: list, body: list):
        self.cucumber: CucumberWrapper = cucumber
        self.path: str = path
        self.name: str = name
        self.tags: list[str] = tags
        self.line: int = line
        self.body: list[str] = body

        self.scenarios: list[Scenario] = []
        self.test_plans: list[TestPlan] = []

        self._find_test_plans()

    def __str__(self):
        return f'Feature (name="{self.name}")'

    def add_scenario(self, scenario: Scenario):
        self.scenarios.append(scenario)

    def repair_tags(self):
        text = self.text
        for scenario in self.scenarios:
            text += scenario.text

        with open(self.path, 'w', encoding='utf-8') as f:
            f.write(text)

    def _find_test_plans(self):
        if self.cucumber.config['test_repository'] == 'xray':
            for test_plan in self.cucumber.test_plans:
                if test_plan.tag in self.tags:
                    self.test_plans.append(test_plan)

    @property
    def _tags_block(self):
        if self.cucumber.config['test_repository'] == 'xray':
            tags = set(self.tags)
            tags_line1 = []
            for test_plan in self.test_plans:
                tags_line1.append('@' + test_plan.tag)
                tags.discard(test_plan.tag)
            tags_line2 = ['@' + tag for tag in sorted(tags)]
            return ' '.join(tags_line1) + '\n' + ' '.join(tags_line2) + '\n'

    @property
    def _name_block(self):
        return 'Feature: ' + self.name + '\n'

    @property
    def _body_block(self):
        return '\n'.join(self.body) + '\n'

    @property
    def text(self):
        return self._tags_block + self._name_block + self._body_block


class CucumberWrapper:

    def __init__(self, config):
        self.config = config
        self.features_root_path: str = config['features']
        self.result: str = config['result']
        self.features_re_path: str = os.path.join(self.features_root_path, '**/*.feature')
        self.test_plans = [TestPlan(k, v) for k, v in config['test_plans'].items()]
        self.test_sets = [TestSet(k, v) for k, v in config['test_sets'].items()]

    @property
    def features(self) -> list[Feature]:
        return self.get_features(self.features_re_path)

    def get_features(self, re_path) -> list[Feature]:
        features = []
        feature_paths = [f.replace(os.sep, '/') for f in glob.glob(re_path, recursive=True)]
        for path in feature_paths:
            features.append(self.read_feature(path))
        return features

    @staticmethod
    def _is_line_of_tags(line):
        return line.strip().startswith('@')

    @staticmethod
    def _is_blank_line(line):
        return not line.strip()

    def read_feature(self, path) -> Feature:
        with open(path, 'r', encoding='utf-8') as feature_file:
            lines = feature_file.readlines()

        feature_index = 0
        for i, line in enumerate(lines):
            if line.strip().startswith('Feature'):
                feature_index = i
                break

        scenario_indexes = []
        for i, line in enumerate(lines):
            if line.strip().startswith('Scenario'):
                scenario_indexes.append(i)

        if not scenario_indexes:
            raise Exception(f'No scenarios found in: "{path}"')

        feature_line = lines[feature_index].strip()
        feature_name = feature_line.split('Feature: ')[1]
        feature_tags = []
        for line in lines[:feature_index]:
            if self._is_line_of_tags(line):
                feature_tags += [x.lstrip('@') for x in line.split()]

        feature_body = []
        for line in lines[feature_index + 1:scenario_indexes[0]]:
            if self._is_line_of_tags(line):
                break
            feature_body.append(line.rstrip())

        feature = Feature(self, path, feature_index + 1, feature_name, feature_tags, feature_body)

        for i, index in enumerate(scenario_indexes):
            scenario_line = lines[index].strip()
            outline = scenario_line.startswith('Scenario Outline: ')
            try:
                name = scenario_line.split('Scenario Outline: ' if outline else 'Scenario: ')[1]
            except IndexError:
                raise Exception(f'No scenario name found at line {index + 1}')

            tags = []
            tag_row = 1
            tag_line = lines[index - tag_row]
            while self._is_line_of_tags(tag_line) or self._is_blank_line(tag_line):
                tags = [x.lstrip('@') for x in lines[index - tag_row].split()] + tags
                tag_row += 1
                tag_line = lines[index - tag_row]

            body = []
            next_index = len(lines) if index == scenario_indexes[-1] else scenario_indexes[i + 1]
            for j in range(index + 1, next_index):
                if self._is_line_of_tags(lines[j]) and 'Examples:' not in lines[j + 1]:
                    break
                body.append(lines[j].rstrip())

            feature.add_scenario(Scenario(self, feature, index + 1, name, outline, tags, body))

        return feature
