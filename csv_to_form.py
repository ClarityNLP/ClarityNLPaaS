import ast
import csv
import json
import os
import re
import string
from os import path, remove

import requests

valid = list(string.digits)
valid.extend(list(string.ascii_letters))
valid.append('_')

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
phenotype "{}" version "1";

// # Referenced libraries #
include ClarityCore version "1.0" called Clarity;

// Termsets
{}

// Data Entities
{}

// Operations
{}


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
cql_vsac_header = '''
        valueset "{}_valueset": '{}'

'''

pt_define = '''

    define "Pt": [Patient]
    
    '''
cql_template = '''
        library Retrieve2 version '1.0'

        using FHIR version '3.0.0'

        include FHIRHelpers version '3.0.0' called FHIRHelpers

        codesystem "LOINC": 'http://loinc.org'
        codesystem "SNOMED": '2.16.840.1.113883.6.96'
        codesystem "RxNorm": 'http://www.nlm.nih.gov/research/umls/rxnorm'
        codesystem "CPT": 'http://www.ama-assn.org/go/cpt'
        codesystem "ICD9": '2.16.840.1.113883.6.42'
        codesystem "ICD10": '2.16.840.1.113883.6.3'
        codesystem USCoreEthnicitySystem: '2.16.840.1.113883.6.238' 
        codesystem RelationshipType: '2.16.840.1.113883.4.642.3.449'

        
        {}

        context Patient
{}
  

{}

{}

'''

# +
cql_concept_template = '''
        define "%s_concepts": Concept {
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
            {}
'''

cql_result_template_res = ''' [{}]'''

cql_result_template_cs = ''' [{}: Code in "{}_concepts"] {}'''

cql_result_template_vs = '''[{}:"{}_valueset"]'''

cql_task_template = '''
define final %s:
    Clarity.CQLExecutionTask({
        "task_index": 0,
        cql: \"\"\"
                %s
             \"\"\"
    });
'''


def format_answer(a):
	return '_'.join(a.split(' ')).lower().replace('"', '').replace('(', '').replace(')', '').replace('.', '') \
		.replace('\n', ' ').strip()


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


def merger(dict1, dict2):
	res = {**dict1, **dict2}
	return res


def cleanup_row(r):
	output_row = dict()
	row = json.loads(json.dumps(r, indent=4, sort_keys=True).replace('\\u00a0', ' ').replace('\\u00ad', '-')
	                 .replace('\\u2265', '>=').replace('\\u2264', '<=').replace('\\u00b3', '3').replace(
		'\\u00b0', ' degrees')
	                 .replace('\\u03b3', 'gamma').replace('\\u03b1', 'alpha').replace('\\u00b5', 'u'))
	for ro in row.keys():
		try:
			new_key = ro.strip().lower()
			output_row[new_key] = row[ro].strip()
		except:
			print('failure to cleanup row')
	return output_row


def write_nlpql_file(output_dir, folder_prefix,
                     group_formatted, termsets, entities, operations, form_name, old_grouping, comment):
	if len(group_formatted.strip()) == 0:
		print('empty group name; nothing to save')
		return
	filename = '{}/{}/{}.nlpql'.format(output_dir, folder_prefix, group_formatted)
	if len(termsets) == 0 and len(entities) == 0 and len(operations) == 0:
		print('no NLPQL attributes found for {}'.format(filename))
	termsets = list(set(termsets))
	entities = list(set(entities))
	operations = list(set(operations))

	if len(entities) > 0:
		with open(filename, 'w') as f:
			ts_string = '\n\n'.join(termsets)
			de_string = '\n\n'.join(entities)
			op_string = '\n\n'.join(operations)
			query = nlpql_template2.format(form_name, ts_string, de_string, op_string)
			f.write(query)


def write_questions_file(output_dir, folder_prefix, form_data, groups, evidence_bundles, evidence_count, suffix=''):
	question_file_name = '{}/{}/questions{}.json'.format(output_dir, folder_prefix, suffix)
	form_data['groups'] = list(groups.keys())
	form_data['evidence_bundles'] = list(evidence_bundles.keys())
	form_data['version'] = get_nlpql_version(question_file_name)
	form_data['questions_with_evidence_count'] = evidence_count

	with open(question_file_name, 'w') as f:
		f.write(json.dumps(form_data, indent=4))

	return form_data


def write_questions_file_v2(output_dir, folder_prefix, form_data, groups, evidence_bundles, evidence_count,
                            all_features, all_rows,
                            suffix='_v2'):
	question_file_name = '{}/{}/questions{}.json'.format(output_dir, folder_prefix, suffix)
	# form_data['groups'] = list(groups.keys())
	# form_data['evidence_bundles'] = list(evidence_bundles.keys())
	# form_data['version'] = get_nlpql_version(question_file_name)
	# form_data['questions_with_evidence_count'] = evidence_count

	# group_formatted = '_'.join(grouping.lower().split(' ')).replace(',', '').replace('_/_', '_')

	new_groupings = dict()
	new_evidences = dict()
	for q in form_data.get('questions', list()):
		group = q.get('group', '')
		group_id = '_'.join(group.lower().split(' ')).replace(',', '').replace('_/_', '_').replace('.', '')
		if group_id not in new_groupings:
			new_groupings[group_id] = list()
		new_q = dict()
		# question type
		q_type = q.get('question_type')

		# get answers
		answers = q.get('answers', list())
		options = list()
		valid_answers = list()
		for a in answers:
			v = a.get('value', '').strip()
			t = a.get('text', '').strip()
			options.append({
				'label': t,
				'value': v
			})
			if len(t) > 0:
				valid_answers.append(t)
		new_q['options'] = options

		# get autofill and defaults
		evidence_bundle = q.get('evidence_bundle', dict())
		autofill = dict()
		default_answer = None

		case_values = dict()
		for evidence in evidence_bundle.keys():
			features = evidence_bundle[evidence]
			rows = all_rows.get(q.get('question_number'))
			if rows:
				for row in rows:
					if row:
						row_feature = row.get('feature', row.get('feature_name', ''))
						default = row.get('default_answer', row.get('default', '')).strip()
						autofill_criteria = row.get('autofill', '')
						autofill_mc = row.get('autofill_mc_answer', row.get('autofill_mc', ''))

						if len(default) > 0 and (
								default in valid_answers or (q_type != 'RADIO' or q_type != 'CHECKBOX')):
							formatted_default = format_answer(default)
							if default and formatted_default and formatted_default != default_answer and \
									(q_type == 'RADIO' or q_type == 'CHECKBOX'):
								print('WARNING: duplicate default on Question {}: {} != {}'.format(
									q.get('question_number', -1000),
									formatted_default,
									default_answer))
							default_answer = formatted_default

						if len(autofill_criteria) and autofill_criteria.upper() != 'EXISTS':
							print(autofill_criteria)
							query = dict()
							fld = "{}.{}.{}".format(evidence, row_feature, autofill_criteria)
							query['field'] = fld
							query['operator'] = '$exists'
							query['criteria'] = True

							case_values[fld] = {
								'queries': [query],
								"value": '$$' + fld
							}
						elif (autofill_criteria.strip().lower() == 'exists' or len(autofill_criteria) == 0) and len(
								autofill_mc) > 0:
							autofill_exist_answer = format_answer(autofill_mc)
							query = dict()
							query['field'] = "{}.{}.pipeline_id".format(evidence, row_feature)
							query['operator'] = '$exists'
							query['criteria'] = True

							if autofill_exist_answer not in case_values:
								case_values[autofill_exist_answer] = {
									'queries': [query],
									"value": autofill_exist_answer
								}
							else:
								case_values[autofill_exist_answer]['queries'].append(query)

		if default_answer:
			autofill['default'] = default_answer
		default_cases = list(case_values.values())
		cases = list()
		for default_case in default_cases:
			case = dict()
			default_queries = default_case.get('queries', list())
			if len(default_queries) > 1:
				# default operator is and - this forces or
				or_op = dict()
				or_op['operator'] = '$or'
				or_op['clauses'] = default_queries
				case['queries'] = [or_op]
				case['value'] = default_case.get('value')
			else:
				case = default_case
			cases.append(case)

		autofill['cases'] = cases

		# map to new data structure
		new_q['id'] = 'question{}'.format(q.get('question_number', -1000))
		new_q['number'] = int(q.get('question_number', -1000))
		new_q['name'] = q.get('question_name')
		new_q['type'] = q_type
		new_q['value'] = ''
		q_evidence = q.get('nlpql_grouping', '')
		if len(q_evidence) > 0:
			new_q['evidence'] = q_evidence

		if len(cases) > 0:
			new_q['autofill'] = autofill

		new_groupings[group_id].append(new_q)

		evidence_bundle = q.get('evidence_bundle', dict())
		for k in evidence_bundle.keys():
			new_evidences[k] = evidence_bundle[k]

	new_form_data = dict()
	new_form_data['name'] = form_data['name']
	new_form_data['slug'] = folder_prefix
	new_form_data['description'] = form_data['description']
	new_form_data['allocated_users'] = form_data['allocated_users']
	new_form_data['groups'] = dict()
	new_form_data['evidences'] = dict()

	new_form_data['groups']['byId'] = dict()
	group_evidences = list()
	question_all_ids = list()
	group_ids = list()
	for g in list(groups.keys()):
		id_name = '_'.join(g.lower().split(' ')).replace(',', '').replace('_/_', '_').replace('.', '')
		new_grouping_mapping = new_groupings.get(id_name, list())
		mapped_group = dict()
		qs = dict()

		id_list = list()
		evidences = set()
		for ngm in new_grouping_mapping:
			the_id = ngm.get('id')
			evidence = ngm.get('evidence', '')
			qs[the_id] = ngm
			id_list.append(the_id)

			if len(evidence) > 0:
				evidences.add(evidence)

		mapped_group['name'] = g
		mapped_group['questions'] = dict()
		mapped_group['questions']['byId'] = qs
		mapped_group['questions']['allIds'] = list(qs.keys())
		mapped_group['evidences'] = list(evidences)

		new_form_data['groups']['byId'][id_name] = mapped_group
		group_ids.append(id_name)
		question_all_ids.extend(id_list)
		group_evidences.extend(list(evidences))

	# new_form_data['groups']['evidences'] = group_evidences
	# new_form_data['groups']['allIds'] = question_all_ids
	new_form_data['groups']['allIds'] = group_ids

	for k in new_evidences.keys():
		new_evidence = dict()
		new_evidence['allIds'] = new_evidences.get(k, list())
		byid = dict()
		for l in new_evidence.get('allIds'):
			byid_item = dict()
			# TODO display stuff

			feature_info = all_features.get(l, dict())
			feature_name_display_name = feature_info.get('feature_name', feature_info.get('feature', '')). \
				replace('_', ' ').strip().title()
			display_type = feature_info.get('display_type', '')
			fhir_resource_type = feature_info.get('fhir_resource_type', '')
			if len(display_type) > 0:
				byid_item['displayType'] = display_type
			else:
				nlp_task_type = feature_info.get('nlp_task_type', '')
				if 'CQL' in nlp_task_type:
					if fhir_resource_type == 'Observation':
						byid_item['displayType'] = 'table'
						byid_item['cols'] = [
							{
								"label": "Date",
								"value": "r.result_display.date"
							},
							{
								"label": "Name",
								"value": "r.code_coding_0_display"
							},
							{
								"label": "Val",
								"value": "`${r.valueQuantity_value} ${r.valueQuantity_code}`"
							}
						]
					elif fhir_resource_type == 'Condition':
						byid_item['displayType'] = 'table'
						byid_item['cols'] = [
							{
								"label": "Date",
								"value": "r.result_display.date"
							},
							{
								"label": "Name",
								"value": "r.code_coding_0_display"
							},
							{
								"label": "Code",
								"value": "r.code_coding_0_code"
							}
						]

					else:
						byid_item['displayType'] = 'cards'
				elif 'ValueExtraction' in nlp_task_type:
					byid_item['displayType'] = 'table'
					byid_item['cols'] = [
						{
							"label": "Date",
							"value": "r.result_display.date"
						},
						{
							"label": "Name",
							"value": "r.text"
						},
						{
							"label": "Val",
							"value": "`${r.value}`"
						}
					]
				else:
					byid_item['displayType'] = 'cards'
			display_name = feature_info.get('feature_display_name', '')
			if len(display_name) > 0:
				byid_item['title'] = display_name
			else:
				if len(fhir_resource_type) > 0:
					byid_item['title'] = '{} {}'.format(feature_name_display_name, fhir_resource_type).strip()
				else:
					byid_item['title'] = '{} Text Mentions'.format(feature_name_display_name).strip()

			byid[l] = byid_item
		new_evidence['byId'] = byid
		new_form_data['evidences'][k] = new_evidence

	with open(question_file_name, 'w') as f:
		f.write(json.dumps(new_form_data, indent=4))


def save_question_to_form_data(q_type, answers, name, question_num, group, evidence, grouping, map_qs, form_data):
	# if not grouping or grouping == '':
	#     grouping = grouping_alt
	print('saving question ', question_num, ' ', name)
	answer_sets = list()
	if q_type != 'DATE' and q_type != 'TEXT':
		for a in answers:
			txt = a.replace('\n', ' ').replace('"', '').strip()
			val = format_answer(a)
			if " = " in txt:
				kv = txt.replace('"', '').split('=')
				if len(kv) == 2:
					answer_sets.append({
						'text': kv[1].strip(),
						'value': kv[0].strip()
					})
				else:
					answer_sets.append({
						'text': txt,
						'value': val
					})
			else:
				answer_sets.append({
					'text': txt,
					'value': val
				})
	this_evidence = dict()
	if evidence and len(grouping) > 0:
		for k in evidence.keys():
			if k == grouping:
				this_evidence[k] = list(set(evidence[k]))
			for v in evidence[k]:
				if v == grouping:
					this_evidence[k] = list(set(evidence[k]))
	new_q = {
		"question_name": name,
		"question_type": q_type,
		"question_number": question_num,
		"group": group,
		"answers": answer_sets,
		"evidence_bundle": this_evidence,
		"nlpql_grouping": grouping
	}
	new_question = True
	question_num = str(question_num)
	old_q = dict()
	for q_ in form_data.get('questions', list()):
		old_q_num = str(q_.get('question_number', ''))
		if old_q_num == question_num:
			new_question = False
			old_q = q_
			break

	if new_question:
		map_qs.append(question_num)
		form_data['questions'].append(new_q)
	else:
		merged_q = merger(old_q, new_q)
		i = 0
		for q_ in form_data.get('questions', list()):
			old_q_num = str(q_.get('question_number', ''))
			if old_q_num == question_num:
				form_data['questions'][i] = merged_q
				break
			i += 1

	evidence = dict()


def get_term_string(_terms):
	if len(_terms) < 1:
		return ''
	_terms = [i.replace('"', '') for i in _terms]
	term_string = '", "'.join(_terms)
	if term_string.strip() != '':
		term_string = '"' + term_string + '"'
		term_string = term_string.replace(', " unspecified",', ',').replace('"",', '')
	return term_string


def map_provider_assertion(terms, termsets, feature_name, features, entities):
	term_string = get_term_string(terms)
	if term_string != '':
		termsets.append(termset_template.format(feature_name, term_string))
		pq = '''Clarity.ProviderAssertion({
      termset: [%s_terms]
    });
                    ''' % feature_name
		pa = basic_data_entity_template.format(feature_name, pq)
		features.append(feature_name)
		entities.append(pa)


def map_term_proximity(terms, terms2, termsets, feature_name, features, entities, word_distance=3):
	term_string = get_term_string(terms)
	term_string2 = get_term_string(terms2)
	if term_string != '' and term_string2 != '':
		termsets.append(termset_template.format(feature_name, term_string))
		f2 = feature_name + '2'
		termsets.append(termset_template.format(f2, term_string2))
		pq = '''    Clarity.TermProximityTask({
        documentset: [Docs],
        "termset1": [%s_terms],
        "termset2": [%s_terms],
        "word_distance": %d,
        "any_order": "True"
    });
                        ''' % (feature_name, f2, word_distance)
		pa = basic_data_entity_template.format(feature_name, pq)
		features.append(feature_name)
		entities.append(pa)


def map_logic(logic, feature_name, features, entities):
	if not logic.startswith('where '):
		logic = 'where ' + logic
	if not logic.endswith(';'):
		logic = logic + ';\n'
	pa = basic_data_entity_template.format(feature_name, logic)
	features.append(feature_name)
	entities.append(pa)


def map_value_extraction(terms, termsets, feature_name, value_min, value_max, value_enum_set, features, entities, values_before_terms):
	map_generic_task('ValueExtraction', terms, termsets, feature_name, value_min, value_max, value_enum_set,
	                 features, entities, values_before_terms=values_before_terms)


def map_generic_task(nlp_task_type, terms, termsets, feature_name, value_min, value_max, value_enum_set,
                     features, entities, values_before_terms=False):
	term_string = get_term_string(terms)
	if term_string.strip() != '':
		termsets.append(termset_template.format(feature_name, term_string))

	v_min = ''
	v_max = ''
	v_values_before_terms = ''
	v_enum_string = ''

	if len(value_min) > 0:
		v_min = ', minimum_value: "{}"'.format(value_min)
	if len(value_max) > 0:
		v_max = ', maximum_value: "{}"'.format(value_max)
	if nlp_task_type == 'ValueExtraction':
		if values_before_terms:
			v_values_before_terms = ', "values_before_terms": "True"'
	if len(value_enum_set) > 0:
		v_enum = ''
		for v in value_enum_set:
			if len(v) == 0:
				continue
			if len(v_enum) > 0:
				v_enum += ', '
			v = v.replace('?', '').replace('"', '').replace("'", '').strip()
			v_enum += ('"{}"'.format(v))
		if len(v_enum) > 0:
			v_enum_string = ', enum_list: [{}],'.format(v_enum)
	if len(terms) > 0:
		terms_attr_string = 'termset: [%s_terms]' % feature_name
	else:
		terms_attr_string = ''
	query_params = ('''
                %s
                 %s
                 %s
                 %s
                 %s
    ''' % (terms_attr_string, v_min, v_max, v_values_before_terms, v_enum_string)).strip()
	pq = '''Clarity.%s({
                 %s});
                               ''' % (nlp_task_type, query_params)
	pq = pq.replace(',});', '});').replace(""",
                 });""", '});')
	pa = basic_data_entity_template.format(feature_name, pq)
	features.append(feature_name)
	entities.append(pa)


def map_cql(codes, code_sys, feature_name, concepts, fhir_resource_type, entities, features, value_set_oid,
            cql_expression, cql_folder, value_min=None, value_max=None):
	cql_concept = ''
	cql_header = ''
	c_string = ''
	if not codes:
		codes = list()
	if len(codes) == 1 and codes[0] == '':
		codes = list()
	if len(codes) > 0:
		for c in codes:
			if len(c_string) > 0:
				c_string += ', \n            '
			code = c.replace('?', '').replace('"', '').replace("'", '')
			c_string += 'Code \'{}\' from "{}"'.format(code, code_sys)
		cql_concept = cql_concept_template % (feature_name, c_string)
		concepts.append(cql_concept)
	if value_set_oid and len(value_set_oid) > 0:
		value_set_oid = value_set_oid.replace('?', '').replace('"', '').replace("'", '')
		cql_define_name = feature_name
		cql_header = cql_vsac_header.format(cql_define_name, value_set_oid)

	if len(cql_expression) > 0:

		cql_res = cql_expression
	else:
		c_string = ''
		resource = fhir_resource_type

		if not resource or len(resource) == 0:
			resource = 'Observation'

		cql_result_members = list()
		#
		# define "Conditions Indicating Sexual Activity":
		#     ["Condition": "Other Female Reproductive Conditions"]
		#     union ["Condition": "Genital Herpes"]
		#     union ["Condition": "Genococcal Infections and Venereal Diseases"]
		#     union ["Condition": "Inflammatory Diseases of Female Reproductive Organs"]
		#     union ["Condition": "Chlamydia"]
		#     union ["Condition": "HIV"]
		#     union ["Condition": "Syphilis"]
		#     union ["Condition": "Complications of Pregnancy, Childbirth and the Puerperium"]

		value_template = 'O where O.value.value > {:.1f} {}'
		value_template_upper = ' and O.value.value < {:.1f}'
		value_template_upper_only = 'O where O.value.value < {:.1f} {}'
		upper_string = ''
		value_string = ''

		if resource == 'Observation':

			if value_max and value_max != '' and (not value_min or value_min == ''):
				try:
					value_string = value_template_upper_only.format((float(value_max)), '')
				except:
					value_string = ''
			else:
				if value_max and value_max != '':
					try:
						upper_string = value_template_upper.format((float(value_max)))
					except Exception as ex:
						upper_string = ''

				if value_min and value_min != '':
					try:
						value_string = value_template.format((float(value_min)), upper_string)
					except:
						value_string = ''


		if not codes:
			codes = list()
		if len(codes) == 1 and codes[0] == '':
			codes = list()
		if len(codes) > 0:
			cql_result_members.append(cql_result_template_cs.format(resource, feature_name, value_string))
		if value_set_oid and len(value_set_oid) > 0:
			cql_result_members.append(cql_result_template_vs.format(resource, feature_name))

		if len(cql_concept) == 0 and len(cql_result_members) == 0:
			cql_result_members.append(cql_result_template_res.format(resource))

		if len(cql_result_members) == 1:
			cql_res = '\t' + cql_result_members[0]
		else:
			cql_res = '''\n\t\t\t\tunion '''.join(cql_result_members)

	if len(cql_res) > 0:
		cql_res = cql_result_template.format(feature_name, cql_res)
		pt_context = ''
		if '"Pt"' in cql_concept or '"Pt"' in cql_res:
			pt_context = pt_define
		cql = cql_template.format(cql_header, pt_context, cql_concept, cql_res)

		entities.append(cql_task_template % (feature_name, cql))
		features.append(feature_name)

		if len(cql_folder) > 0:
			filename = '{}/{}.cql'.format(cql_folder, feature_name)
			with open(filename, 'w') as f:
				f.write(cql)


def get_nlpql_version(question_file_name):
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
	return version


def get_feature_name(name, all_features):
	remove_it = string.punctuation
	remove_it = remove_it.replace("_", "")
	pattern = r"[{}]".format(remove_it)

	name = re.sub(pattern, "", name)
	# if name in all_features:
	# 	sep = name.split('_')
	# 	if len(sep) <= 1:
	# 		name = name + '_1'
	# 	else:
	# 		last = sep[-1]
	# 		if last.isdigit():
	# 			next_int = int(last) + 1
	# 			sep = sep[0:-1]
	# 			name = '_'.join(sep) + '_' + str(next_int)
	# 			if name in all_features:
	# 				return get_feature_name(name, all_features)
	# 		else:
	# 			name = name + '_1'
	# 			if name in all_features:
	# 				return get_feature_name(name, all_features)
	return name


def parse_questions_from_feature_csv(folder_prefix='4100r4',
                                     form_name="Form 4100 R4.0",
                                     file_name='/Users/charityhilton/Downloads/feature2question.csv',
                                     output_dir='/Users/charityhilton/repos/CIBMTR_knowledge_base',
                                     description=None):
	if not description:
		description = form_name
	output_folder_path = os.path.join(output_dir, folder_prefix)
	print(output_folder_path)
	if not os.path.exists(output_folder_path):
		os.mkdir(output_folder_path)
	cql_folder = os.path.join(output_folder_path, 'cql')
	if not os.path.exists(cql_folder):
		os.mkdir(cql_folder)

	feature_names = set()

	temp = False
	if file_name.startswith('http'):
		r = requests.get(file_name)
		temp = True

		file_name = '/tmp/{}.csv'.format(folder_prefix)
		with open(file_name, 'wb') as f:
			f.write(r.content)

	with open(file_name, 'r', encoding='utf-8', errors='ignore') as csv_file:
		reader = csv.DictReader(csv_file, delimiter=',', quotechar='"')

		form_data = {
			"name": form_name,
			"owner": "gatech",
			"description": description,
			"allocated_users": ["admin"],
			"groups": list(),
			"questions": list(),
			"evidence_bundles": list()
		}

		n = 0
		groups = dict()
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
		evidence_bundles = dict()

		all_features = dict()
		all_rows = dict()

		name = None
		group = None
		q_type = None
		answers = list()
		map_qs = list()

		last_row = None
		for r in reader:
			row = cleanup_row(r)
			print(row)
			r_evidence_bundle = row.get('evidence_bundle', '')
			r_num = row.get('#', '')
			r_group = row.get('group', '')
			r_question_name = row.get('question_name', r.get('name', 'Unknown'))
			r_answers = row.get('answers', '')
			r_type = row.get('type', row.get('question_type', ''))
			r_feature_name = row.get('feature_name', '').replace(' ', '')
			r_fhir_resource_type = row.get('fhir_resource_type', '')
			r_code_system = row.get('code_system', '')
			r_codes = row.get('codes', '')
			# r_valueset_oid = row.get('valueset_oid', '')
			r_valueset_oid = ''
			r_cql_expression = row.get('cql_expression', '')
			r_nlp_task_type = row.get('nlp_task_type', '')
			r_terms = row.get('text_terms', row.get('terms', ''))
			r_terms2 = row.get('text_terms2', row.get('terms2', ''))
			r_word_distance = row.get('word_distance', row.get('word_proximity', row.get('term_proximity', '3')))
			r_value_min = row.get('value_min', '')
			r_value_max = row.get('value_max', '')
			r_value_enum_set = row.get('value_enum_set', '')
			r_logic = row.get('logic', '')
			r_report_tags = row.get('report_tags', '')
			r_report_types = row.get('report_types', '')
			r_values_before_terms = row.get('values_before_terms', 'f')
			if not r_values_before_terms or len(r_values_before_terms.strip()) == 0:
				r_values_before_terms = 'f'
			r_values_before_terms = r_values_before_terms.lower()[0]
			if r_values_before_terms == 't' or r_values_before_terms == '1':
				values_before_terms = True
			else:
				values_before_terms = False


			l_nlp_task_type = r_nlp_task_type.lower()
			if len(r_nlp_task_type) == 0:
				if len(r_codes) > 0 or len(r_valueset_oid) > 0:
					r_nlp_task_type = 'CQLExecutionTask'
				elif len(r_terms) == 0:
					if len(r_value_min) > 0 or len(r_value_max) > 0 or len(r_value_enum_set) > 0:
						r_nlp_task_type = 'ValueExtraction'
				elif len(logic) > 0:
					r_nlp_task_type = 'Logic'
			else:
				if 'cql' in l_nlp_task_type:
					if len(r_fhir_resource_type) == 0 and len(r_cql_expression) == 0:
						r_nlp_task_type = ''
				elif 'value' in l_nlp_task_type or 'term' in l_nlp_task_type or 'assertion' in l_nlp_task_type:
					if len(r_terms) == 0:
						r_nlp_task_type = ''
					else:
						if 'value' in l_nlp_task_type and len(r_value_min) == 0 and len(r_value_max) == 0 and \
								len(r_value_enum_set) == 0:
							r_nlp_task_type = 'ProviderAssertion'
				elif 'logic' in l_nlp_task_type:
					if len(r_logic) == 0:
						r_nlp_task_type = ''

			if 'value' in l_nlp_task_type and len(r_value_min) == 0 and len(r_value_max) == 0 and \
					len(r_value_enum_set) == 0:
				r_nlp_task_type = 'ProviderAssertion'

			if len(r_evidence_bundle) > 0 and len(r_num) == 0:
				if last_row:
					last_r_num = last_row.get('#', '')
					last_r_group = last_row.get('group', '')
					last_r_question_name = last_row.get('question_name', '')
					last_r_answers = last_row.get('answers', '')
					last_r_type = last_row.get('type', row.get('question_type', ''))

					print('no question, using last {}'.format(last_r_num))
					r_num = last_r_num
					r_group = last_r_group
					r_question_name = last_r_question_name
					r_answers = last_r_answers
					r_type = last_r_type
				else:
					print('no question')
					continue

			last_row = row
			if r_num == '':
				continue

			if grouping and len(grouping) > 0 and grouping != r_evidence_bundle:
				new_grouping = True

			old_grouping = grouping
			if len(r_feature_name) > 0 and not old_grouping:
				old_grouping = r_evidence_bundle
			else:
				old_grouping = ''
			if not grouping:
				grouping = ''
			group_formatted = '_'.join(grouping.lower().split(' ')).replace(',', '').replace('_/_', '_')

			last_question = question_num
			if last_question and str(last_question) != str(r_num):
				save_question_to_form_data(q_type, answers, name, last_question, group, evidence,
				                           group_formatted, map_qs, form_data)

			question_num = r_num
			answers = [x.strip() for x in r_answers.split(',') if len(r_answers) > 0]
			grouping = r_evidence_bundle
			feature_name = get_feature_name(r_feature_name, feature_names)
			row['feature_name'] = feature_name
			name = r_question_name
			q_type = r_type
			group = r_group
			evidence_bundle = r_evidence_bundle
			fhir_resource_type = r_fhir_resource_type
			code_sys = r_code_system
			codes = [x.strip() for x in r_codes.split(',') if len(r_codes) > 0]
			valueset_oid = r_valueset_oid
			cql_expression = r_cql_expression
			nlp_task_type = r_nlp_task_type
			terms = list(set([x.strip().lower() for x in r_terms.split(',') if len(r_terms) > 0]))
			terms2 = list(set([x.strip().lower() for x in r_terms2.split(',') if len(r_terms2) > 0]))
			if is_numeric(r_word_distance):
				word_distance = int(r_word_distance)
			else:
				word_distance = 3
			value_min = r_value_min
			value_max = r_value_max
			if len(r_value_enum_set) > 0:
				value_enum_set = r_value_enum_set.split(',')
			else:
				value_enum_set = []
			logic = r_logic.strip()

			if feature_name not in feature_names:
				feature_names.add(feature_name)

			all_features[feature_name] = row
			if r_num not in all_rows:
				all_rows[r_num] = list()
			all_rows[r_num].append(row)

			if len(group) > 0:
				groups[group] = ''

			no_evidence = False
			if len(r_evidence_bundle) == 0 or len(r_feature_name) == 0:
				print('no evidence for question {}'.format(question_num))
				new_grouping = True
				no_evidence = True

			if new_grouping:
				nlpql_form_name = (folder_prefix + ' - ' + group_formatted).replace('_', ' ')
				write_nlpql_file(output_dir, folder_prefix, group_formatted, termsets, entities, operations,
				                 nlpql_form_name,
				                 old_grouping, comment)
				group_number += 1
				termsets = list()
				entities = list()
				operations = list()
				concepts = list()
				comment = ''
				new_grouping = False

			if not no_evidence:
				feature_name = ''.join([t for t in feature_name if t in valid])
				if len(name.strip()) == 0:
					continue

				q_type = q_type.upper()
				if q_type == 'MS' or q_type == 'MULTIPLE_SELECT' or q_type == 'MULTIPLE SELECT' or q_type == 'CHECKBOX':
					q_type = 'CHECKBOX'
				elif q_type == 'MC' or q_type == 'MULTIPLE_CHOICE' or q_type == 'MULTIPLE CHOICE' or q_type == 'RADIO':
					q_type = 'RADIO'
				elif q_type == 'TEXT+MC' or q_type == 'TEXT_WITH_MULTIPLE_CHOICE' or q_type == \
						'TEXT WITH MULTIPLE CHOICE':
					# q_type = 'TEXT_WITH_MULTIPLE_CHOICE'
					q_type = 'TEXT'
				elif q_type == "DT" or q_type == "DATETIME" or q_type == 'TIMESTAMP' or q_type == 'DATE':
					q_type = "DATE"
				else:
					q_type = 'TEXT'

				features = list()
				if len(evidence_bundle) > 0:
					evidence_bundles[evidence_bundle] = ''

				if len(feature_name) == 0 or len(evidence_bundle) == 0 or len(nlp_task_type) == 0:
					continue
				comment += '\n\n'
				comment += json.dumps(row, indent=4, sort_keys=True)

				if len(terms) > 0 and len(terms2) > 0 and 'proximity' in l_nlp_task_type:
					map_term_proximity(terms, terms2, termsets, feature_name, features, entities,
					                   word_distance=word_distance)
				elif len(terms) > 0 and 'assertion' in l_nlp_task_type:
					map_provider_assertion(terms, termsets, feature_name, features, entities)
				elif len(logic) > 0 and 'logic' in l_nlp_task_type:
					map_logic(logic, feature_name, features, entities)
				elif len(terms) > 0 and 'value' in l_nlp_task_type:
					map_value_extraction(terms, termsets, feature_name, value_min, value_max, value_enum_set, features,
					                     entities, values_before_terms)
				elif len(cql_expression) > 0 or len(r_fhir_resource_type) > 0:
					map_cql(codes, code_sys, feature_name, concepts, fhir_resource_type, entities, features,
					        valueset_oid, cql_expression, cql_folder, value_min=value_min, value_max=value_max)
				else:
					map_generic_task(nlp_task_type, terms, termsets, feature_name, value_min, value_max, value_enum_set,
					                 features, entities)
				if evidence_bundle not in evidence:
					evidence[evidence_bundle] = list()
				evidence[evidence_bundle].append(feature_name)
				if new_question:
					evidence_count += 1
			n += 1

		old_grouping = grouping
		group_formatted = '_'.join(grouping.lower().split(' ')).replace(',', '').replace('_/_', '_')
		nlpql_form_name = (folder_prefix + ' - ' + group_formatted).replace('_', ' ')
		write_nlpql_file(output_dir, folder_prefix,
		                 group_formatted, termsets, entities, operations, nlpql_form_name, old_grouping, comment)
		save_question_to_form_data(q_type, answers, name, question_num, group, evidence, group_formatted,
		                           map_qs, form_data)
		write_questions_file(output_dir, folder_prefix, form_data, groups, evidence_bundles, evidence_count,
		                     suffix='')
		write_questions_file(output_dir, folder_prefix, form_data, groups, evidence_bundles, evidence_count,
		                     suffix='_v1')
		write_questions_file_v2(output_dir, folder_prefix, form_data, groups, evidence_bundles, evidence_count,
		                        all_features, all_rows, suffix='_v2')
		print(evidence_count)
		if temp:
			remove(file_name)
		return form_data


if __name__ == "__main__":
	# parse_questions_from_feature_csv(folder_prefix='covid19',
	#                                  form_name="COVID-19",
	#                                  file_name='https://docs.google.com/spreadsheet/ccc?key=1w9VcIxVJXYh8mX7RGtxo7rHyq-r64bbzFQs6dGz0Vuk&output=csv',
	#                                  output_dir='/Users/chilton9/repos/custom_nlpql',
	#                                  description='COVID-19 Case Definition')
	# parse_questions_from_feature_csv(folder_prefix='death',
	#                                  form_name="US Death Certificate",
	#                                  file_name='https://docs.google.com/spreadsheet/ccc?key=1J_JqRjjryjaJE-fB9nNcBb9mQNL3cl7dx_vhbG95XHE&output=csv',
	#                                  output_dir='/Users/charityhilton/repos/custom_nlpql',
	#                                  description='US Death Certificate')
	# parse_questions_from_feature_csv(folder_prefix='setnet',
	#                                  form_name="SET-NET",
	#                                  file_name='https://docs.google.com/spreadsheet/ccc?key=1hGwgzRVItB-SE6tnysSwj9EjFPc1MJ6ov1EumJHn_PA&output=csv',
	#                                  output_dir='/Users/charityhilton/repos/custom_nlpql',
	#                                  description='CDC Surveillance for Emerging Threats to Pregnant Women and Infants')

	cibmtr_key = ''
	parse_questions_from_feature_csv(folder_prefix='4100r4',
	                                 form_name="Form 4100 R4.0",
	                                 #file_name='https://docs.google.com/spreadsheet/ccc?key={}&output=csv'.format(cibmtr_key),
                                     file_name='/Users/chilton9/Downloads/CIBMTR-Form_4100_Mapping - FeatureToQuestionMapping (3).csv',
	                                 output_dir='/Users/chilton9/repos/custom_nlpql',
	                                 description='CIBMTR Cellular Therapy Essential Data Follow-Up')
	# parse_questions_from_feature_csv(folder_prefix='fluoroquinolone',
	#                                  form_name="Fluoroquinolone Valvular Events",
	#                                  file_name='https://docs.google.com/spreadsheet/ccc?key=11GGj6SPwLLjKoNVS3vp-YtVOs5facig6Py5491bHVQQ&output=csv',
	#                                  output_dir='/Users/charityhilton/repos/custom_nlpql',
	#                                  description='Data on patients who have exposure to fluoroquinolones and show valvular abnormalities')
