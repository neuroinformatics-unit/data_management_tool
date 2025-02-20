import os
import shutil

import pytest
from base import BaseTest

from datashuttle import DataShuttle
from datashuttle.configs import canonical_configs
from datashuttle.utils import validation
from datashuttle.utils.custom_exceptions import NeuroBlueprintError


class TestPersistentSettings(BaseTest):

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_persistent_settings_name_templates(self, project):
        """
        Test the 'name_templates' option that is stored in persistent
        settings and adds a regexp to validate subject and session
        names against.

        Here we test the mechanisms of getting and setting `name_templates`
        and then check that all validation are performing as expected when
        using them.
        """
        # Load name_templates and check defaults are as expected
        name_templates = project.get_name_templates()

        assert len(name_templates) == 3
        assert name_templates["on"] is False
        assert name_templates["sub"] is None
        assert name_templates["ses"] is None

        # Set some new settings and check they become persistent
        sub_regexp = "sub-\d_id-.?.?_random-.*"
        ses_regexp = "ses-\d\d_id-.?.?.?_random-.*"

        new_name_templates = {
            "on": True,
            "sub": sub_regexp,
            "ses": ses_regexp,
        }

        project.set_name_templates(new_name_templates)

        project_reload = DataShuttle(project.project_name)

        reload_name_templates = project_reload.get_name_templates()

        assert len(reload_name_templates) == 3
        assert reload_name_templates["on"] is True
        assert reload_name_templates["sub"] == sub_regexp
        assert reload_name_templates["ses"] == ses_regexp

        # Check the validation works correctly based on settings
        # when making sub / ses folders
        good_sub = "sub-2_id-ab_random-helloworld"
        bad_sub = "sub-3_id-abC_random-helloworld"
        good_ses = "ses-33_id-xyz_random-helloworld"
        bad_ses = "ses-33_id-xyz_ranDUM-helloworld"

        # Bad sub name
        with pytest.raises(NeuroBlueprintError) as e:
            project.create_folders("rawdata", bad_sub)
        assert (
            str(e.value) == "The name: "
            "sub-3_id-abC_random-helloworld "
            "does not match the template: "
            "sub-\d_id-.?.?_random-.*"
        )

        # Good sub name (should not raise)
        project.create_folders("rawdata", good_sub)

        # Bad ses name
        with pytest.raises(NeuroBlueprintError) as e:
            project.create_folders("rawdata", good_sub, bad_ses)

        assert (
            str(e.value) == "The name: "
            "ses-33_id-xyz_ranDUM-helloworld "
            "does not match the template: "
            "ses-\\d\\d_id-.?.?.?_random-.*"
        )

        # Good ses name (should not raise)
        project.create_folders("rawdata", good_sub, good_ses)

        # Now just test the other validation functions explicitly
        # here as well to avoid duplicate of test setup.

        # Test `validate_names_against_project()`
        with pytest.raises(NeuroBlueprintError) as e:
            validation.validate_names_against_project(
                project.cfg,
                "rawdata",
                [bad_sub],
                ses_names=None,
                local_only=True,
                error_or_warn="error",
                name_templates=reload_name_templates,
            )
        assert "does not match the template:" in str(e.value)

        bad_sub_path = project.cfg["local_path"] / "rawdata" / bad_sub
        os.makedirs(bad_sub_path)

        # Test `validate_project()`
        with pytest.raises(NeuroBlueprintError) as e:
            project.validate_project("rawdata", "error", local_only=True)
        shutil.rmtree(bad_sub_path)

        assert "sub-3_id-abC_random-helloworld" in str(e.value)

        # Turn it off the `name_template` option
        # and check a bad ses name does not raise
        reload_name_templates["on"] = False
        project.set_name_templates(reload_name_templates)

        project.create_folders("rawdata", good_sub, "ses-02")

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_persistent_settings_tui(self, project):
        """
        Test persistent settings for the project that
        determine display of the TUI. First check defaults
        are correct, change every one and save, then check
        they are correct on re-load.
        """

        # test all defaults
        settings = project._load_persistent_settings()
        tui_settings = settings["tui"]
        assert tui_settings == self.get_settings_default()

        # change all defaults
        new_tui_settings = self.get_settings_changed()

        project._update_persistent_setting("tui", new_tui_settings)

        # Reload and check
        project = DataShuttle(project.project_name)

        reloaded_settings = project._load_persistent_settings()
        assert reloaded_settings["tui"] == new_tui_settings

    @pytest.mark.parametrize("project", ["local", "full"], indirect=True)
    def test_bypass_validation(self, project):
        """
        Check bypass validation which will allow folder
        creation even when validation fails. Check it is
        off by default, turn on, check bad name can be created.
        Reload, turn off, check for error on attempting to create
        bad name.
        """
        # should not raise
        project.create_folders("rawdata", "sub-@@@", bypass_validation=True)

        project = DataShuttle(project.project_name)

        with pytest.raises(BaseException) as e:
            project.create_folders("rawdata", "sub-@@@")

        assert (
            "The name: name: sub-@@@, contains characters which are not alphanumeric"
            in str(e)
        )

    def get_settings_default(self):
        """
        Hard-coded default settings that should mirror `canonical_configs`
        and should be changed whenever the canonical configs are changed.
        This is to protect against accidentally changing these configs.
        """
        default_settings = {
            "create_checkboxes_on": {},
            "transfer_checkboxes_on": {
                "all": {"on": True, "displayed": True},
                "all_datatype": {"on": False, "displayed": True},
                "all_non_datatype": {"on": False, "displayed": True},
            },
            "top_level_folder_select": {
                "create_tab": "rawdata",
                "toplevel_transfer": "rawdata",
                "custom_transfer": "rawdata",
            },
            "bypass_validation": False,
            "overwrite_existing_files": "never",
            "dry_run": False,
        }
        default_settings["create_checkboxes_on"] = {
            key: {"on": True, "displayed": True}
            for key in canonical_configs.get_broad_datatypes()
        } | {
            key: {"on": False, "displayed": False}
            for key in canonical_configs.quick_get_narrow_datatypes()
        }

        default_settings["transfer_checkboxes_on"].update(
            {
                key: {"on": False, "displayed": True}
                for key in canonical_configs.get_broad_datatypes()
            }
            | {
                key: {"on": False, "displayed": False}
                for key in canonical_configs.quick_get_narrow_datatypes()
            }
        )

        return default_settings

    def get_settings_changed(self):
        """
        The default settings with every possible setting changed.
        """
        changed_settings = {
            "create_checkboxes_on": {},
            "transfer_checkboxes_on": {
                "all": {"on": False, "displayed": False},
                "all_datatype": {"on": True, "displayed": False},
                "all_non_datatype": {"on": True, "displayed": False},
            },
            "top_level_folder_select": {
                "create_tab": "derivatives",
                "toplevel_transfer": "derivatives ",
                "custom_transfer": "derivatives",
            },
            "bypass_validation": True,
            "overwrite_existing_files": "always",
            "dry_run": True,
        }

        changed_settings["create_checkboxes_on"] = {
            key: {"on": False, "displayed": False}
            for key in canonical_configs.get_broad_datatypes()
        } | {
            key: {"on": False, "displayed": False}
            for key in canonical_configs.quick_get_narrow_datatypes()
        }

        changed_settings["transfer_checkboxes_on"].update(
            {
                key: {"on": True, "displayed": False}
                for key in canonical_configs.get_broad_datatypes()
            }
            | {
                key: {"on": True, "displayed": True}
                for key in canonical_configs.quick_get_narrow_datatypes()
            }
        )
        return changed_settings
