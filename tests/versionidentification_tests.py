# Vane 2.0: A web application vulnerability assessment tool.
# Copyright (C) 2017-  Delve Labs inc.
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from unittest import TestCase
from unittest.mock import MagicMock, call
from os.path import join, dirname
from openwebvulndb.common.models import FileSignature, File, FileList

from vane.versionidentification import VersionIdentification
from vane.filefetcher import FetchedFile
from fixtures import html_file_to_hammertime_response


class TestVersionIdentification(TestCase):

    def setUp(self):
        self.version_identification = VersionIdentification()

        self.readme_fetched_file = FetchedFile(path="readme.html", hash="12345")
        self.style_css_fetched_file = FetchedFile(path="style.css", hash="09876")

        self.readme_1_signature = FileSignature(hash=self.readme_fetched_file.hash, versions=["1.0"])
        self.readme_2_signature = FileSignature(hash="23456", versions=["2.0"])
        self.readme_file = File(path="readme.html", signatures=[self.readme_1_signature, self.readme_2_signature])

        self.style_css_signature = FileSignature(hash=self.style_css_fetched_file.hash, versions=["1.0", "2.0"])
        self.style_css_file = File(path="style.css", signatures=[self.style_css_signature])

        self.file_list = FileList(key="", producer="", files=[self.readme_file, self.style_css_file])

    def test_get_possible_versions_for_fetched_file(self):
        file_list = FileList(key="wordpress", producer="", files=[self.readme_file])

        versions = self.version_identification._get_possible_versions_for_fetched_file(self.readme_fetched_file,
                                                                                       file_list)

        self.assertEqual(versions, self.readme_1_signature.versions)

    def test_identify_version(self):
        file_list = FileList(producer="unittest", key="wordpress", files=[self.readme_file, self.style_css_file])
        fetched_files = [self.readme_fetched_file, self.style_css_fetched_file]

        version = self.version_identification.identify_version(fetched_files, file_list)

        self.assertEqual(version, "1.0")

    def test_identify_version_find_closest_match_when_one_file_is_missing(self):
        login_js_signature_1 = FileSignature(hash="11111", versions=["1.0"])
        login_js_signature_2 = FileSignature(hash="22222", versions=["2.0"])
        login_js_file = File(path="login.js", signatures=[login_js_signature_1, login_js_signature_2])

        file_list = FileList(producer="unittest", key="wordpress", files=[self.readme_file, self.style_css_file,
                                                                          login_js_file])
        fetched_login = FetchedFile(path="login.js", hash="11111")
        fetched_files = [fetched_login, self.style_css_fetched_file]

        version = self.version_identification.identify_version(fetched_files, file_list)

        self.assertEqual(version, "1.0")

    def test_identify_version_not_affected_if_one_file_has_no_common_version_with_others(self):
        login_js_file = File(path="login.js", signatures=[FileSignature(hash="11111", versions=["1.0"])])
        file_no_common_version = File(path="test.html", signatures=[FileSignature(hash="22222", versions=["1.5"])])

        self.file_list.files.extend([login_js_file, file_no_common_version])
        fetched_login = FetchedFile(path="login.js", hash="11111")
        fetched_file_no_common_version = FetchedFile(path="test.html", hash="22222")
        fetched_files = [fetched_login, self.style_css_fetched_file, self.readme_fetched_file,
                         fetched_file_no_common_version]

        version = self.version_identification.identify_version(fetched_files, self.file_list)
        self.assertEqual(version, "1.0")

    def test_identify_version_use_exposed_version_in_source_files_to_choose_between_multiple_possible_versions(self):
        self.version_identification._get_possible_versions = MagicMock(return_value={"4.7.1", "4.7.2", "4.7.3"})
        source_files = ["homepage.html", "wp-login.php"]
        self.version_identification.find_versions_in_source_files = MagicMock(return_value={"4.7.2"})

        version = self.version_identification.identify_version("fetched_files", "identification_files",
                                                               files_exposing_version=source_files)

        self.assertEqual(version, "4.7.2")
        self.version_identification.find_versions_in_source_files.assert_called_once_with(source_files)

    def test_identify_version_return_none_if_no_version_found(self):
        file_list = FileList(producer="unittest", key="wordpress", files=[self.style_css_file])

        version = self.version_identification.identify_version([self.readme_fetched_file], file_list)

        self.assertIsNone(version)

    def test_get_most_reliable_version_return_input_version_if_only_one_version(self):
        version = self.version_identification.get_most_reliable_version(fetched_files_versions={"4.9.4"})
        self.assertEqual(version, "4.9.4")

    def test_get_most_reliable_version_return_lowest_version_if_more_than_one_version_from_single_source(self):
        versions = {"4.9.3", "4.9.2", "4.9.4"}

        best_version0 = self.version_identification.get_most_reliable_version(fetched_files_versions=versions)
        best_version1 = self.version_identification.get_most_reliable_version(source_files_versions=versions)

        self.assertEqual(best_version0, "4.9.2")
        self.assertEqual(best_version1, "4.9.2")

    def test_get_most_reliable_version_return_lowest_common_version_if_using_two_sources_and_one_source_has_more_than_one_version(self):
        versions_from_fetched_files = {"4.9.3", "4.9.2", "4.9.4"}
        versions_from_source_files = {"4.9.3", "4.9.2", "4.9.1"}

        best_version = self.version_identification.get_most_reliable_version(
            fetched_files_versions=versions_from_fetched_files, source_files_versions=versions_from_source_files)

        self.assertEqual(best_version, "4.9.2")

    def test_get_most_reliable_version_use_only_fetched_files_version_if_source_files_versions_has_no_version_in_common_and_confidence_level_is_100(self):
        versions_from_fetched_files = {"4.9.3", "4.9.2", "4.9.4"}
        versions_from_source_files = {"4.9.0", "4.9.1"}
        self.version_identification.set_confidence_level_of_fetched_files(100)

        best_version = self.version_identification.get_most_reliable_version(
            fetched_files_versions=versions_from_fetched_files, source_files_versions=versions_from_source_files)

        self.assertEqual(best_version, "4.9.2")

    def test_get_most_reliable_version_use_lowest_source_files_versions_with_same_minor_if_no_version_in_common_and_confidence_level_is_not_100(self):
        versions_from_fetched_files = {"4.9.3", "4.9.2", "4.9.4"}
        versions_from_source_files = {"4.9.0", "4.9.1"}
        self.version_identification.set_confidence_level_of_fetched_files(86)

        best_version = self.version_identification.get_most_reliable_version(
            fetched_files_versions=versions_from_fetched_files, source_files_versions=versions_from_source_files)

        self.assertEqual(best_version, "4.9.0")

    def test_get_most_reliable_version_use_source_files_versions_with_same_major_if_no_version_with_common_minor(self):
        versions_from_fetched_files = {"4.9.3", "4.9.2", "4.9.4"}
        versions_from_source_files = {"4.8.0", "4.8.1"}
        self.version_identification.set_confidence_level_of_fetched_files(51)

        best_version = self.version_identification.get_most_reliable_version(
            fetched_files_versions=versions_from_fetched_files, source_files_versions=versions_from_source_files)

        self.assertEqual(best_version, "4.8.0")

    def test_get_most_reliable_version_return_none_if_no_version_with_common_major(self):
        versions_from_fetched_files = {"4.9.3", "4.9.2", "4.9.4"}
        versions_from_source_files = {"3.8.1", "3.9.0"}
        self.version_identification.set_confidence_level_of_fetched_files(51)

        best_version = self.version_identification.get_most_reliable_version(
            fetched_files_versions=versions_from_fetched_files, source_files_versions=versions_from_source_files)

        self.assertEqual(best_version, None)

    def test_get_lowest_version(self):
        versions = ["1.3.0", "1.3.1", "4.7.0", "2.7.6", "1.0.12"]

        version = self.version_identification._get_lowest_version(versions)

        self.assertEqual(version, "1.0.12")

    def test_find_versions_in_source_files_search_versions_in_each_source_file(self):
        self.version_identification._find_versions_in_file = MagicMock(return_value=set())

        self.version_identification.find_versions_in_source_files(["source_file0", "source_file1"])

        self.version_identification._find_versions_in_file.assert_has_calls([call("source_file0"), call("source_file1")])

    def test_find_versions_in_source_files_return_versions_present_in_any_file(self):
        versions_from_file = {"1.2.1", "1.11.2", "4.7.5"}
        self.version_identification._find_versions_in_file = MagicMock(return_value=versions_from_file)

        version = self.version_identification.find_versions_in_source_files(["source_file0", "source_file1"])

        self.assertEqual(version, versions_from_file)

    def test_find_versions_in_file_return_set_of_strings_that_match_version_pattern(self):
        homepage0 = html_file_to_hammertime_response(join(dirname(__file__), "samples/delvelabs_homepage.html"))
        homepage1 = html_file_to_hammertime_response(join(dirname(__file__), "samples/sample_homepage.html"))
        login_page0 = html_file_to_hammertime_response(join(dirname(__file__), "samples/delvelabs_login.html"))
        login_page1 = html_file_to_hammertime_response(join(dirname(__file__), "samples/canola_login.html"))
        homepage0_versions = {"4.7.5"}
        login_page0_versions = {"4.7.5"}
        homepage1_versions = {"4.2.2", "1.11.2", "1.2.1", "3.2"}
        login_page1_versions = {"4.2.2"}

        homepage0_result = self.version_identification._find_versions_in_file(homepage0)
        login_page0_result = self.version_identification._find_versions_in_file(login_page0)
        homepage1_result = self.version_identification._find_versions_in_file(homepage1)
        login_page1_result = self.version_identification._find_versions_in_file(login_page1)

        self.assertEqual(homepage0_versions, homepage0_result)
        self.assertEqual(login_page0_versions, login_page0_result)
        self.assertEqual(homepage1_versions, homepage1_result)
        self.assertEqual(login_page1_versions, login_page1_result)

    def test_find_versions_in_file_confirm_version_with_generator_meta_tag_if_present(self):
        """Some wordpress sites have the tag <meta name="generator" content="WordPress X.Y.Z" />"""
        homepage0 = html_file_to_hammertime_response(join(dirname(__file__), "samples/delvelabs_homepage.html"))
        homepage1 = html_file_to_hammertime_response(join(dirname(__file__), "samples/canola_homepage.html"))
        homepage0_versions = {"4.7.5"}
        homepage1_versions = {"4.2.2"}

        homepage0_result = self.version_identification._find_versions_in_file(homepage0)
        homepage1_result = self.version_identification._find_versions_in_file(homepage1)

        self.assertEqual(homepage0_versions, homepage0_result)
        self.assertEqual(homepage1_versions, homepage1_result)

    def test_find_versions_in_file_find_version_in_wp_links_opml_php_file(self):
        file = html_file_to_hammertime_response(join(dirname(__file__), "samples/wp-links-opml.php"))
        version_exposed = {"4.7.5"}

        found_version = self.version_identification._find_versions_in_file(file)

        self.assertEqual(version_exposed, found_version)
