#!/usr/bin/env python
"""Utility script to list html files which might be missing i18n strings."""
import _init_path  # noqa: F401  Imported for its side effect of setting PYTHONPATH
import re
import sys
from pathlib import Path
from enum import Enum
from scripts.solr_builder.solr_builder.fn_to_cli import FnToCLI
import glob

# This is a list of files that had pre-existing i18n errors/warnings at the time this script was created.
# Chip away at these and remove them from the exclude list (except where otherwise noted).
EXCLUDE_LIST = {
    "openlibrary/templates/design.html",
    "openlibrary/templates/internalerror.html",
    "openlibrary/templates/login.html",
    "openlibrary/templates/permission_denied.html",
    "openlibrary/templates/showmarc.html",
    "openlibrary/templates/status.html",
    "openlibrary/templates/work_search.html",
    "openlibrary/templates/showia.html",
    "openlibrary/templates/about/index.html",
    "openlibrary/templates/account/import.html",
    "openlibrary/templates/account/readinglog_stats.html",
    "openlibrary/templates/account/email/forgot.html",
    "openlibrary/templates/admin/attach_debugger.html",
    "openlibrary/templates/admin/block.html",
    "openlibrary/templates/admin/graphs.html",
    "openlibrary/templates/admin/history.html",
    "openlibrary/templates/admin/imports.html",
    "openlibrary/templates/admin/imports_by_date.html",
    "openlibrary/templates/admin/loans.html",
    "openlibrary/templates/admin/loans_table.html",
    "openlibrary/templates/admin/solr.html",
    "openlibrary/templates/admin/spamwords.html",
    "openlibrary/templates/admin/sponsorship.html",
    "openlibrary/templates/admin/sync.html",
    "openlibrary/templates/admin/inspect/memcache.html",
    "openlibrary/templates/admin/inspect/store.html",
    "openlibrary/templates/admin/ip/index.html",
    "openlibrary/templates/admin/memory/index.html",
    "openlibrary/templates/admin/memory/object.html",
    "openlibrary/templates/admin/people/index.html",
    "openlibrary/templates/admin/people/view.html",
    "openlibrary/templates/books/add.html",
    "openlibrary/templates/books/custom_carousel.html",
    "openlibrary/templates/books/mobile_carousel.html",
    "openlibrary/templates/books/works-show.html",
    "openlibrary/templates/books/edit/edition.html",
    "openlibrary/templates/books/edit/web.html",
    "openlibrary/templates/contact/spam/sent.html",
    "openlibrary/templates/email/case_created.html",
    "openlibrary/templates/home/loans.html",
    "openlibrary/templates/home/popular.html",
    "openlibrary/templates/home/returncart.html",
    "openlibrary/templates/jsdef/LazyAuthorPreview.html",
    "openlibrary/templates/jsdef/LazyWorkPreview.html",
    "openlibrary/templates/languages/index.html",
    "openlibrary/templates/lib/history.html",
    "openlibrary/templates/lib/nav_foot.html",
    "openlibrary/templates/lists/export_as_html.html",
    "openlibrary/templates/lists/feed_updates.html",
    "openlibrary/templates/lists/widget.html",
    "openlibrary/templates/my_books/dropdown_content.html",
    "openlibrary/templates/my_books/primary_action.html",
    "openlibrary/templates/observations/review_component.html",
    "openlibrary/templates/publishers/index.html",
    "openlibrary/templates/publishers/view.html",
    "openlibrary/templates/recentchanges/header.html",
    "openlibrary/templates/recentchanges/render.html",
    "openlibrary/templates/recentchanges/add-book/path.html",
    "openlibrary/templates/recentchanges/default/view.html",
    "openlibrary/templates/recentchanges/edit-book/path.html",
    "openlibrary/templates/recentchanges/merge/comment.html",
    "openlibrary/templates/recentchanges/merge/path.html",
    "openlibrary/templates/recentchanges/undo/view.html",
    "openlibrary/templates/search/snippets.html",
    "openlibrary/templates/site/alert.html",
    "openlibrary/templates/site/stats.html",
    "openlibrary/templates/type/about/view.html",
    "openlibrary/templates/type/author/rdf.html",
    "openlibrary/templates/type/author/view.html",
    "openlibrary/templates/type/edition/view.html",
    "openlibrary/templates/type/language/view.html",
    "openlibrary/templates/type/list/edit.html",
    "openlibrary/templates/type/list/exports.html",
    "openlibrary/templates/type/local_id/view.html",
    "openlibrary/templates/type/page/view.html",
    "openlibrary/templates/type/template/edit.html",
    "openlibrary/templates/type/template/view.html",
    "openlibrary/templates/type/type/view.html",
    "openlibrary/templates/type/work/view.html",
    "openlibrary/macros/FulltextSnippet.html",
    "openlibrary/macros/ManageLoansButtons.html",
    "openlibrary/macros/ManageWaitlistButton.html",
    "openlibrary/macros/QueryCarousel.html",
    "openlibrary/macros/RecentChangesAdmin.html",
    "openlibrary/macros/RecentChangesUsers.html",
    "openlibrary/macros/SearchResults.html",
    "openlibrary/macros/databarWork.html",
    "openlibrary/macros/WorkInfo.html",
    # These are excluded because they require more info to fix
    "openlibrary/templates/books/edit.html",
    "openlibrary/templates/history/sources.html",
    # This can't be fixed because it's not in the i18n directories
    "openlibrary/admin/templates/admin/index.html",
    # These can't be fixed since they're rendered as static html
    "static/offline.html",
    "static/status-500.html",
}

default_directories = ('openlibrary/templates/', 'openlibrary/macros/')


class Errtype(str, Enum):
    WARN = "\033[93mWARN\033[0m"
    ERR = "\033[91mERRO\033[0m"
    SKIP = "\033[94mSKIP\033[0m"


skip_directive = r"# detect-missing-i18n-skip-line"
regex_skip_inline = r"\$" + skip_directive
regex_skip_previous_line = r"^\s*\$?" + skip_directive

# Assumptions:
# - Not concerned about HTML elements whose untranslated contents follow a newline, i.e. <p>\nsome untranslated text\n<p>.
# - Don't want to flag false positives where > characters are not part of tags, so this regex looks for a complete opening tag.
# TODO: replace the huge punctuation array with \p{L} - only supported in pip regex and not re
punctuation = r"[\(\)\{\}\[\]\/\\:;\-_\s+=*^%#\.•·\?♥|≡0-9,!xX✓×@\"'†★]"
htmlents = r"&[a-z0-9]+;"
variables = r"\$:?[^\s]+|\$[^\s\(]+[\(][^\)]+[\)]|\$[^\s\[]+[\[][^\]]+[\]]|\$[\{][^\}]+[\}]|%\(?[a-z_]+\)?|\{\{[^\}]+\}\}"
urls_domains = r"https?:\/\/[^\s]+|[a-z\-]+\.[A-Za-z]{2}[a-z]?"

opening_tag_open = r"<(?!code|link|!--)[a-z][^>]*?"
opening_tag_end = r"[^\/\-\s]>"
opening_tag_syntax = opening_tag_open + opening_tag_end
ignore_after_opening_tag = (
    r"(?![<\r\n]|$|\\\$\$|\$:?_?\(|\$:?ungettext\(|(?:"
    + punctuation
    + r"|"
    + htmlents
    + r"|"
    + variables
    + r"|"
    + urls_domains
    + r")+(?:[\r\n<]|$))"
)
warn_after_opening_tag = r"\$\(['\"]"

i18n_element_missing_regex = opening_tag_syntax + ignore_after_opening_tag
i18n_element_warn_regex = opening_tag_syntax + warn_after_opening_tag

attr_syntax = r"(title|placeholder|alt)="
ignore_double_quote = (
    r"\"(?!\$:?_?\(|\$:?ungettext\(|\\\$\$|(?:"
    + punctuation
    + r"|"
    + variables
    + r"|"
    + urls_domains
    + r")*\")"
)
ignore_single_quote = (
    r"\'(?!\$:?_?\(|\$:?ungettext\(|\\\$\$|(?:"
    + punctuation
    + r"|"
    + variables
    + r"|"
    + urls_domains
    + r")*\')"
)

i18n_attr_missing_regex = (
    opening_tag_open
    + attr_syntax
    + r"(?:"
    + ignore_double_quote
    + r"|"
    + ignore_single_quote
    + r")[^>]*?>"
)
i18n_attr_warn_regex = opening_tag_open + attr_syntax + warn_after_opening_tag


def terminal_underline(text: str) -> str:
    return f"\033[4m{text}\033[0m"


def print_analysis(
    errtype: str,
    filename: Path,
    details: str,
    spacing_base: int,
    line_number: int = 0,
    line_position: int = 0,
):
    linestr = (
        f":{line_number}:{line_position}"
        if line_number > 0 and line_position > 0
        else ""
    )
    filestring = f'{filename}{linestr}'
    print(
        '\t'.join(
            [errtype, terminal_underline(filestring).ljust(spacing_base + 12), details]
        )
    )


def main(files: list[Path], skip_excluded: bool = True):
    """
    :param files: The html files to check for missing i18n. Leave empty to run over all html files.
    :param skip_excluded: If --no-skip-excluded is supplied as an arg, files in the EXCLUDE_LIST slice will be processed
    """

    if not files:
        files = [
            Path(file_path)
            for ddir in default_directories
            for file_path in glob.glob(f'{ddir}**/*.html', recursive=True)
        ]

    # Figure out how much padding to put between the filename and the error output
    longest_filename_length = max(len(str(f)) for f in files)
    spacing_base = longest_filename_length + len(':XXX:XXX')

    errcount: int = 0
    warnings: int = 0

    for file in files:
        contents = file.read_text()
        lines = contents.splitlines()

        if skip_excluded and str(file) in EXCLUDE_LIST:
            print_analysis(Errtype.SKIP, file, "", spacing_base)
            continue

        for line_number, line in enumerate(lines, start=1):

            includes_error_element = re.search(i18n_element_missing_regex, line)
            includes_warn_element = re.search(i18n_element_warn_regex, line)
            includes_error_attribute = re.search(i18n_attr_missing_regex, line)
            includes_warn_attribute = re.search(i18n_attr_warn_regex, line)

            char_index = -1
            # Element with untranslated elements
            if includes_error_element:
                char_index = includes_error_element.start()
                errtype = Errtype.ERR
            # Element with bypassed elements
            elif includes_warn_element:
                char_index = includes_warn_element.start()
                errtype = Errtype.WARN
            # Element with untranslated attributes
            elif includes_error_attribute:
                char_index = includes_error_attribute.start()
                errtype = Errtype.ERR
            # Element with bypassed attributes
            elif includes_warn_attribute:
                char_index = includes_warn_attribute.start()
                errtype = Errtype.WARN

            # Don't proceed if the line doesn't match any of the four cases.
            else:
                continue

            preceding_text = line[:char_index]
            regex_match = line[char_index:]

            # Don't proceed if the line is likely commented out or part of a $: function.
            if "<!--" in preceding_text or "$:" in preceding_text:
                continue

            # Don't proceed if skip directive is included inline.
            if re.search(regex_skip_inline, regex_match):
                continue

            # Don't proceed if the previous line is a skip directive.
            if re.match(regex_skip_previous_line, lines[line_number - 2]):
                continue

            print_position = char_index + 1
            print_analysis(
                errtype,
                file,
                regex_match,
                spacing_base,
                line_number,
                print_position,
            )

            if errtype == Errtype.WARN:
                warnings += 1
            elif errtype == Errtype.ERR:
                errcount += 1

    print(
        f"{len(files)} file{'s' if len(files) != 1 else ''} scanned. {errcount} error{'s' if errcount != 1 else ''} found."
    )
    if errcount > 0 or warnings > 0:
        print(
            "Learn how to fix these errors by reading our i18n documentation: https://github.com/internetarchive/openlibrary/wiki/Internationalization#internationalization-i18n-developers-guide"
        )

    if errcount > 0:
        sys.exit(1)


if __name__ == "__main__":
    FnToCLI(main).run()
