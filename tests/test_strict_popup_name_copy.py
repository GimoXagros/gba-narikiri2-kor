"""Reuse synchronous ownership/ABI checks with the actual popup consumer target."""
import test_strict_honorific_append as common
import strict_popup_name_copy


class PopupNameCopyTest(common.HonorificAppendTest):
    component=strict_popup_name_copy
    consumer=0x08025D00
