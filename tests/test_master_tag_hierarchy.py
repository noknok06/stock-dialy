"""MasterTag の親子関係（parent）バリデーションの回帰テスト。

ユーザー個別タグ(Tag)に親子関係を追加した際、標準タグ(MasterTag)側にも
同じ2階層ルール（親を持つタグは親になれない・親子は同じ軸）を入れ忘れると、
docs/analysis_templates/tag_master.md が想定する「細分タグ」構造と
DB上のMasterTagの状態が矛盾しうるため、モデルのclean()で機械的に防ぐ。
"""
import pytest
from django.core.exceptions import ValidationError

from tags.models import MasterTag


@pytest.mark.django_db
class TestMasterTagHierarchy:
    def test_child_can_be_linked_to_parent(self):
        parent = MasterTag.objects.create(name='エネルギー', axis='theme')
        child = MasterTag.objects.create(name='LNG', axis='theme', parent=parent)
        child.full_clean()
        assert child.parent_id == parent.id
        assert parent.children.count() == 1

    def test_self_parent_rejected(self):
        tag = MasterTag.objects.create(name='AI', axis='theme')
        tag.parent = tag
        with pytest.raises(ValidationError):
            tag.full_clean()

    def test_grandparent_rejected(self):
        """階層は2段階まで。親自身が誰かの子である場合は孫を作れない。"""
        grandparent = MasterTag.objects.create(name='エネルギー', axis='theme')
        parent = MasterTag.objects.create(name='LNG', axis='theme', parent=grandparent)
        grandchild = MasterTag(name='LNGトレーディング', axis='theme', parent=parent)
        with pytest.raises(ValidationError):
            grandchild.full_clean()

    def test_axis_mismatch_rejected(self):
        parent = MasterTag.objects.create(name='エネルギー', axis='theme')
        child = MasterTag(name='高配当', axis='capital_policy', parent=parent)
        with pytest.raises(ValidationError):
            child.full_clean()

    def test_tag_with_children_cannot_become_child(self):
        parent = MasterTag.objects.create(name='エネルギー', axis='theme')
        MasterTag.objects.create(name='LNG', axis='theme', parent=parent)
        other_root = MasterTag.objects.create(name='脱炭素', axis='theme')

        parent.parent = other_root
        with pytest.raises(ValidationError):
            parent.full_clean()
