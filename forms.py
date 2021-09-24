import util


def get_forms_stub():
    client = util.mongo_client()
    results = list()
    try:
        db = client[util.mongo_db]

        for res in db.smart_forms.find({}):
            results.append(res)
    except Exception as e:
        util.log(e, util.ERROR)
    finally:
        client.close()
    return results
