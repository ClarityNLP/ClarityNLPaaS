import ast
import csv
import json
import os
import string
from os import path

import nltk
from nltk.corpus import stopwords

nlpql_template = '''
// Phenotype library name
phenotype "Form {}, Question {}" version "1";

// # Referenced libraries #
include ClarityCore version "1.0" called Clarity;

// Data Entities
{}

// Operations
{}

// Comments
/*
{}

*/

'''

nlpql_template2 = '''
// Phenotype library name
phenotype "Form {}, Bundle {}" version "1";

// # Referenced libraries #
include ClarityCore version "1.0" called Clarity;

// Termsets
{}

// Data Entities
{}

// Operations
{}

// Comments
/*
{}

*/

'''

termset_template = '''
termset {}_terms: [
    {}
];

'''

basic_data_entity_template = '''
define final {}:
    {}
'''

cql_template = '''
        library Retrieve2 version '1.0'

        using FHIR version '3.0.0'

        include FHIRHelpers version '3.0.0' called FHIRHelpers

        codesystem "LOINC": 'http://loinc.org'
        codesystem "SNOMED": 'urn:oid:2.16.840.1.113883.6.96'
        codesystem "RxNorm": 'http://www.nlm.nih.gov/research/umls/rxnorm'
        codesystem "CPT": 'http://www.ama-assn.org/go/cpt'
        codesystem "ICD9": '2.16.840.1.113883.6.42'
        codesystem "ICD10": '2.16.840.1.113883.6.3'

        context Patient

{}

{}

'''

# +
cql_concept_template = '''
        define "%s_concept": Concept {
            %s
        }

'''

# -

# Code '26464-8' from "LOINC",
# Code '804-5' from "LOINC",
# Code '6690-2' from "LOINC",
# Code '49498-9' from "LOINC"

# +

cql_result_template = '''
        define "{}":
            [{}: Code in "{}_concept"]
'''

cql_task_template = '''
define final %s:
    Clarity.CQLExecutionTask({
        "task_index": 0,
        cql: \"\"\"
                %s
             \"\"\"
    });
'''


def question_number(line):
    question_string = ''
    spl = line.split(':')
    try:
        n = int(spl[-1])
    except ValueError:
        n = -1

    if len(spl) > 1:
        question_string = spl[0]
    if n != -1 and n < 10000:
        return question_string, n
    else:
        return None, None


def value_set(set_name, final_str, *args):
    args_str = '{ \n \t\t'

    for k, v in args[0].items():

        if isinstance(v, float):
            v = '"{}"'.format(v)

        args_str += '{}: {}, \n \t\t'.format(k, v)

    args_str += "}"

    val_set = """
    define {}:
        Clarity.ValueExtraction({});         
    """.format(set_name, args_str)

    val_set += final_str

    return val_set


def gen_feature_name(rhs, comparator, lhs):
    op_name = "AnyVal"

    if comparator == "<":
        op_name = "Lt"
    elif comparator == ">":
        op_name = "Gt"

    elif comparator == "<=":
        op_name = "Leq"

    elif comparator == ">=":
        op_name = "Geq"

    elif comparator == "==":
        op_name = "Equals"

    feature_name = "{}{}{}".format(rhs[0], op_name, str(lhs))

    final_str = """

    define final has{}:
        where {}.value {} {};

    """.format(feature_name, feature_name, comparator, lhs)

    return feature_name, final_str


def convert_expr_to_value_extraction(expr, feature_name=None):
    kwargs_to_pass = {}

    val_extr_ast = ast.parse(expr)

    code_ast = ast.parse(expr)

    lhs = list()
    rhs = None
    comparator = None

    for node in ast.walk(code_ast):
        # we need to be able to handle n-grams that are actually a single concept/measurement, etc.
        if isinstance(node, ast.Name):
            lhs.append(node.id)

        # this is our (numeric) LHS
        elif isinstance(node, ast.Num):
            rhs = node.n

        # grab our operator and convert it to a string representation
        elif isinstance(node, ast.Compare):
            op = node.ops[0]
            if isinstance(op, ast.Lt):
                comparator = "<"
            elif isinstance(op, ast.Gt):
                comparator = ">"
            elif isinstance(op, ast.LtE):
                comparator = "<="
            elif isinstance(op, ast.GtE):
                comparator = ">="
            elif isinstance(op, ast.Eq):
                comparator = "=="

    kwargs_to_pass["termset"] = "{}".format([x.replace("_", " ") for x in lhs])

    # leq and geq are handled the same as >; < per clarity value extraction docs
    if comparator in ("<", "<="):
        kwargs_to_pass["maximum_value"] = '"{}"'.format(rhs)
    elif comparator in (">", ">="):
        kwargs_to_pass["minimum_value"] = '"{}"'.format(rhs)

    elif comparator == "==":
        kwargs_to_pass["minimum_value"] = '"{}"'.format(rhs)
        kwargs_to_pass["maximum_value"] = '"{}"'.format(rhs)

    if feature_name is None:
        feature_name, final_str = gen_feature_name(lhs, comparator, rhs)

    return value_set(feature_name, final_str, {k: v for k, v in kwargs_to_pass.items()})


# input_str = [["ANC >= 500" ],["ANC == 200"], ["FiO2 < 0.4"]]
# json_obj = json.loads(json.dumps(input_str))

# out = ''
# for x in json_obj:
#     test = convert_expr_to_value_extraction("""{}""".format(str(x[0])))
#     out += test

# -

def is_numeric(test):
    try:
        int(test)
        float(test)
        return True
    except ValueError:
        return False


def cleanup_name(name):
    name = name.strip().lower()
    exclude = set(string.punctuation)
    no_punct_name = ''.join(ch for ch in name if ch not in exclude)
    stop_words = stopwords.words('english')
    stop_words.append('eg')
    stop_words.append('days')
    stop_words.append('date')
    stop_words.append('current')
    stop_words.append('recent')
    stop_words.append('since')
    keys = no_punct_name.lower().split(' ')
    keys = [word for word in keys if word not in stop_words]
    keys = [word for word in keys if len(word) > 1]
    keys = [word for word in keys if not is_numeric(word)]
    if len(keys) > 5:
        keys = keys[0:4]
    clean_name = "_".join(keys).replace('__', '_')
    key_length = len(keys)
    if clean_name.endswith('_'):
        clean_name = clean_name[0:-1]
    return clean_name, key_length


def merger(dict1, dict2):
    res = {**dict1, **dict2}
    return res


def parse_questions_from_feature_csv(folder_prefix='4100r4',
                                     form_name="Form 4100 R4.0",
                                     file_name='/Users/charityhilton/Downloads/feature2question.csv',
                                     output_dir='/Users/charityhilton/repos/CIBMTR_knowledge_base'):
    if not os.path.exists(os.path.join(output_dir, folder_prefix)):
        os.mkdir(os.path.join(output_dir, folder_prefix))

    with open(file_name, 'r', encoding='utf-8', errors='ignore') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')

        form_data = {
            "name": form_name,
            "owner": "gatech",
            "allocated_users": ["admin"],
            "groups": list(),
            "questions": list(),
            "evidence_bundles": list()
        }

        n = 0

        groups = set()
        grouping = None
        new_grouping = False
        last_question = None
        new_question = False
        question_num = None
        termsets = list()
        entities = list()
        operations = list()
        concepts = list()
        comment = ''
        group_number = 1
        evidence_count = 0

        evidence = dict()
        evidence_bundles = set()

        name = None
        group = None
        q_type = None
        answers = list()
        evidence_bundle = None
        map_qs = list()

        last_row = None
        for r in reader:
            row = json.loads(json.dumps(r, indent=4, sort_keys=True).replace('\\u00a0', ' ').replace('\\u00ad', '-')
                             .replace('\\u2265', '>=').replace('\\u2264', '<=').replace('\\u00b3', '3').replace(
                '\\u00b0', ' degrees')
                             .replace('\\u03b3', 'gamma').replace('\\u03b1', 'alpha').replace('\\u00b5', 'u'))

            if len(row['evidence_bundle']) > 0 and len(row['#']) == 0:

                if last_row:
                    print('no question, using last {}'.format(last_row['#']))
                    row['#'] = last_row['#']
                    row['group'] = last_row['group']
                    row['question_name'] = last_row['question_name']
                    row['answers'] = last_row['answers']
                    row['type'] = last_row['type']
                else:
                    print('no question')

            last_row = row
            if row['#'] == '':
                continue

            if grouping and grouping != row['evidence_bundle']:
                new_grouping = True

            old_grouping = grouping
            if question_num and last_question and str(last_question) != str(row['#'].strip()):
                if question_num in map_qs:
                    for i in range(len(form_data['questions'])):
                        q = form_data['questions'][i]
                        if int(q.get('question_number', -1)) == int(question_num):
                            merged = merger(q.get('evidence_bundle'), evidence)
                            form_data['questions'][i]['evidence_bundle'] = merged
                else:
                    print('saving question ', last_question)
                    answer_sets = list()
                    if q_type != 'DATE' and q_type != 'TEXT':
                        for a in answers:
                            answer_sets.append({
                                'text': a.replace('\n', ' ').strip(),
                                'value': '_'.join(a.split(' ')).lower().replace('(', '').replace(')', '').replace('.',
                                                                                                                  '')
                                    .replace('\n', ' ').strip()
                            })
                    q = {
                        "question_name": name,
                        "question_type": q_type,
                        "question_number": question_num,
                        "group": group,
                        "answers": answer_sets,
                        "evidence_bundle": evidence,
                        "nlpql_grouping": grouping
                    }
                    map_qs.append(question_num)
                    form_data['questions'].append(q)
                    evidence = dict()
            last_question = question_num
            # #,question_name,answers,group,type,evidence_bundle,DoneBy,feature_name,fhir_resource_type,code_system,
            # codes,valueset_oid,nlp_task_type,text_terms,value_min,value_max,value_enum_set,value_extractor_ast,logic,
            # notes

            if not old_grouping:
                old_grouping = row['evidence_bundle'].strip()

            question_num = row['#'].strip()
            answers = [x.strip() for x in row.get('answers', '').strip().split(',')]
            grouping = row['evidence_bundle'].strip()
            feature_name = row['feature_name'].strip()
            name = row.get('question_name', row.get('name', 'Unknown')).strip()
            q_type = row.get('type', 'TEXT').strip()
            group = row['group'].strip()
            evidence_bundle = row['evidence_bundle'].strip()
            fhir_resource_type = row['fhir_resource_type'].strip()
            code_sys = row['code_system'].strip()
            codes = [x.strip() for x in row['codes'].strip().split(',')]
            valueset_oid = row['valueset_oid'].strip()
            nlp_task_type = row['nlp_task_type'.strip()].lower()
            terms = [x.strip() for x in row['text_terms'].strip().split(',')]
            value_min = row['value_min'].strip()
            value_max = row['value_max'].strip()
            value_enum_set = row['value_enum_set'].strip().split(',')
            logic = row['logic'].strip()
            group_formatted = '_'.join(old_grouping.strip().lower().split(' ')).replace(',', '').replace('_/_', '_')

            no_evidence = False
            if len(row['evidence_bundle']) == 0 or len(row['feature_name']) == 0:
                print('no evidence for question {}'.format(question_num))
                new_grouping = True
                no_evidence = True

            if new_grouping:
                if len(termsets) == 0 and len(entities) == 0 and len(operations) == 0 and len(concepts) == 0:
                    print('no query for grouping {}'.format(group_formatted))
                else:
                    with open('{}/{}/{}.nlpql'.format(output_dir, folder_prefix,
                                                      group_formatted),
                              'w') as f:
                        ts_string = '\n\n'.join(termsets)
                        de_string = '\n\n'.join(entities)
                        op_string = '\n\n'.join(operations)
                        query = nlpql_template2.format(form_name, old_grouping, ts_string, de_string, op_string,
                                                       comment)
                        f.write(query)

                group_number += 1
                termsets = list()
                entities = list()
                operations = list()
                concepts = list()
                comment = ''
                new_grouping = False
                # form, group, termsets, data entities, operations, comments

            if not no_evidence:
                valid = list(string.digits)
                valid.extend(list(string.ascii_letters))
                valid.append('_')

                feature_name = ''.join([t for t in feature_name if t in valid])
                if len(name.strip()) == 0:
                    continue

                if q_type == 'MS':
                    q_type = 'MULTIPLE_SELECT'
                if q_type == 'MC':
                    q_type = 'MULTIPLE_CHOICE'
                if q_type == 'TEXT+MC':
                    q_type = 'TEXT_WITH_MULTIPLE_CHOICE'

                features = list()
                if len(group) > 0:
                    groups.add(group)
                if len(evidence_bundle) > 0:
                    evidence_bundles.add(evidence_bundle)

                if len(feature_name) == 0 or len(evidence_bundle) == 0 or len(nlp_task_type) == 0:
                    continue
                comment += '\n\n'
                comment += json.dumps(row, indent=4, sort_keys=True)

                if len(terms) > 0 and 'assertion' in nlp_task_type:
                    term_string = '", "'.join(terms)
                    if term_string.strip() != '':
                        term_string = '"' + term_string + '"'
                        term_string = term_string.replace(', " unspecified",', ',')
                        termsets.append(termset_template.format(feature_name, term_string))
                        pq = '''Clarity.ProviderAssertion({
          termset: [%s_terms]
        });
                        ''' % feature_name
                        pa = basic_data_entity_template.format(feature_name, pq)
                        features.append(feature_name)
                        entities.append(pa)
                elif len(logic) > 0 and 'logic' in nlp_task_type:
                    if not logic.startswith('where '):
                        logic = 'where ' + logic
                    if not logic.endswith(';'):
                        logic = logic + ';\n'
                    pa = basic_data_entity_template.format(feature_name, logic)
                    features.append(feature_name)
                    entities.append(pa)
                elif len(terms) > 0 and 'value' in nlp_task_type:
                    term_string = '", "'.join(terms)
                    if term_string.strip() != '':
                        term_string = '"' + term_string + '"'
                        term_string = term_string.replace(', " unspecified",', ',')
                        termsets.append(termset_template.format(feature_name, term_string))

                        v_min = ''
                        v_max = ''
                        v_enum_string = ''

                        if len(value_min) > 0:
                            v_min = ',minimum_value: "{}"'.format(value_min)
                        if len(value_max) > 0:
                            v_max = ',maximum_value: "{}"'.format(value_max)
                        if len(value_enum_set) > 0:
                            v_enum = ''
                            for v in value_enum_set:
                                if len(v) == 0:
                                    continue
                                if len(v_enum) > 0:
                                    v_enum += ', '
                                v = v.replace('?', '').replace('"', '').replace("'", '')
                                v_enum += ('"{}"'.format(v))
                            if len(v_enum) > 0:
                                v_enum_string = ', enum_list: [{}]'.format(v_enum)
                        pq = '''Clarity.ValueExtraction({
                  termset: [%s_terms]
                  %s
                  %s
                  %s
                });
                                ''' % (feature_name, v_min, v_max, v_enum_string)
                        pa = basic_data_entity_template.format(feature_name, pq)
                        features.append(feature_name)
                        entities.append(pa)
                elif (len(codes) > 0 or len(valueset_oid) > 0) and 'cql' in nlp_task_type:
                    c_string = ''
                    for c in codes:
                        if len(c_string) > 0:
                            c_string += ', \n            '
                        code = c.replace('?', '').replace('"', '').replace("'", '')
                        c_string += 'Code \'{}\' from "{}"'.format(code, code_sys)
                    cql_concept = cql_concept_template % (feature_name, c_string)
                    concepts.append(cql_concept)
                    resource = fhir_resource_type

                    cql_res = cql_result_template.format(feature_name, resource, feature_name)
                    cql = cql_template.format(cql_concept, cql_res)
                    entities.append(cql_task_template % (feature_name, cql))
                    features.append(feature_name)

                if evidence_bundle not in evidence:
                    evidence[evidence_bundle] = list()
                evidence[evidence_bundle].append(feature_name)
                if new_question:
                    evidence_count += 1

            n += 1

        print('saving question ', last_question)
        answer_sets = list()
        if q_type != 'DATE' and q_type != 'TEXT':
            for a in answers:
                answer_sets.append({
                    'text': a.replace('\n', ' ').strip(),
                    'value': '_'.join(a.split(' ')).lower().replace('(', '').replace(')', '').replace('.',
                                                                                                      '')
                        .replace('\n', ' ').strip()
                })
        q = {
            "question_name": name,
            "question_type": q_type,
            "question_number": question_num,
            "group": group,
            "answers": answer_sets,
            "evidence_bundle": evidence,
            "nlpql_grouping": grouping
        }
        map_qs.append(question_num)
        form_data['questions'].append(q)
        evidence = dict()
        form_data['groups'] = list(groups)
        form_data['evidence_bundles'] = list(evidence_bundles)

        question_file_name = '{}/{}/questions.json'.format(output_dir, folder_prefix)
        if path.exists(question_file_name):
            with open(question_file_name) as json_file:
                prev_form_data = json.load(json_file)
                prev_version = prev_form_data.get('version')
                if not prev_version:
                    version = "0.0.1"
                else:
                    version_segments = prev_version.split('.')
                    version_segments = [i for i in version_segments if i]
                    version = ''
                    try:
                        version_int = int(version_segments[-1]) + 1
                    except Exception as ex:
                        version_int = 1
                        print(ex)

                    for s in version_segments[:-1]:
                        version = version + s
                        version = version + '.'

                    version += str(version_int)
        else:
            version = "0.0.1"
        form_data['version'] = version

        with open(question_file_name, 'w') as f:
            form_data['questions_with_evidence_count'] = evidence_count
            f.write(json.dumps(form_data, indent=4))

        with open('{}/{}/{}.nlpql'.format(output_dir, folder_prefix,
                                          group_formatted),
                  'w') as f:
            ts_string = '\n\n'.join(termsets)
            de_string = '\n\n'.join(entities)
            op_string = '\n\n'.join(operations)
            query = nlpql_template2.format(form_name, old_grouping, ts_string, de_string, op_string,
                                           comment)
            f.write(query)
        print(evidence_count)
        return form_data


if __name__ == "__main__":
    nltk.download('stopwords')
    # parse_questions_from_feature_csv(folder_prefix='4100r4',
    #                                  form_name="Form 4100 R4.0",
    #                                  file_name='/Users/charityhilton/Downloads/feature2question.csv',
    #                                  output_dir='/Users/charityhilton/repos/custom_nlpql')
    # parse_questions_from_feature_csv(folder_prefix='afib',
    #                                  form_name="Atrial Fibrilation",
    #                                  file_name='./custom_query/afib.csv',
    #                                  output_dir='./custom_query/output')
    parse_questions_from_feature_csv(folder_prefix='afib',
                                     form_name="Atrial Fibrilation",
                                     file_name='./nlpql/afib/afib.csv',
                                     output_dir='/Users/charityhilton/repos/custom_nlpql')
