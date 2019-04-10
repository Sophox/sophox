# import sys
#
# from metabot.Properties import *
# from metabot.processor import Cache, get_sitelink, Processor
#
#
# def taginfo_counts():
#     taginfo = Cache.taginfo.get()
#     return {v['key']: v['count_all'] for v in taginfo['data']}
#
#
# def item_list_to_qid_dict(items):
#     return {v['id']: v for v in items}
#
#
# def items_by_sitelink(items, filter_prefix=None):
#     result = {}
#     for item in items:
#         sl = get_sitelink(item)
#         if not sl or (filter_prefix and not sl.startswith(filter_prefix)):
#             continue
#         if sl in result:
#             raise ValueError(f"Sitelink {sl} is the same for {result[sl]['id']} and {item['id']}")
#         result[sl] = item
#     return result
#
#
#
# opts = {
#     'new': True,
#     'old': True,
#     'autogen_keys': True,
#     'throw': False,
#     'props': {
#         P_INSTANCE_OF.id,
#         P_IMAGE_DEPRECATED.id,
#         P_IMAGE.id,
#         P_STATUS.id,
#         P_KEY_TYPE.id,
#         P_TAG_KEY.id,
#         P_REF_URL.id,
#         P_KEY_ID.id,
#         P_TAG_ID.id,
#         P_ROLE_ID.id,
#         P_GROUP.id,
#     },
#     'ignore_qid': {
#         'Q104',
#         'Q108',
#         'Q1191',
#         'Q171',
#         'Q3',
#         'Q4',
#         'Q4666',
#         'Q501',
#         'Q6',
#         'Q890',
#         'Q261',
#         'Q7565',
#     }
# }
#
# # --- Cached.pages.regenerate()
# # --- Cached.taginfo.regenerate()
# # --- Cached.tagusage.regenerate()
#
#
# # items_by_strid(P_KEY_ID, fix_multiple=True)
# # items_by_strid(P_TAG_ID, fix_multiple=True)
#
# # Cached.description.regenerate()
# # Cached.descriptionParsed.regenerate()
# #
# Cache.items.regenerate()
#
# fix_sitelinks_and_ids(opts)
#
#
# # template = None
# # templ_params = None
# # if not filter:
# #     filter = ['KeyDescription', 'ValueDescription', 'RelationDescription', 'Deprecated']
# # elif type(filter) is str:
# #     filter = [filter]
# #
# # for (templ, params) in textlib.extract_templates_and_params(content, True, True):
# #     if templ not in filter:
# #         continue
# #     if templ_params:
# #         print(f'More than one template {templ} found in page {title}')
# #         continue
# #     template = templ
# #     templ_params = params
# #
# # if not templ_params:
# #     # print(f'No relevant templates found in {title}')
# #     return None
