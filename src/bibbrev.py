from __future__ import print_function
from bibtexparser.bparser import BibTexParser
from bibtexparser.customization import homogeneize_latex_encoding
from bibtexparser.bwriter import to_bibtex
from argparse import ArgumentParser, ArgumentTypeError
import os
import sys
import codecs
import logging
import re
from fuzzywuzzy import fuzz

logging.basicConfig()
logger = logging.getLogger('bibbreviate')

# TODO implement a best guess pass, based on the 'rules' of abbreviation.
# TODO create a utility to update the journal list


def determine_path():
    """Borrowed from wxglade.py"""
    try:
        root = __file__
        if os.path.islink(root):
            root = os.path.realpath(root)
        return os.path.dirname(os.path.abspath(root))
    except:
        print("I'm sorry, but something is wrong.")
        print("There is no __file__ variable. Please contact the author.")
        sys.exit()


def load_abbrevs(fn, reverse=False):
    # This load trick from
    # http://stackoverflow.com/questions/4842057/python-easiest-way-to-ignore-blank-lines-when-reading-a-file
    abbrevs = [_f for _f in (line.rstrip()
                            for line in codecs.open(fn, encoding='utf-8')) if _f]
    abbrevs = [line.split('=') for line in abbrevs]
    abbrevs = [[line[0].strip(), line[1].strip()] for line in abbrevs]
    if not reverse:
        abbrevs = {line[0].strip().lower(): line[1].strip()
                   for line in abbrevs}
    else:
        abbrevs = {line[1].strip().lower(): line[0].strip()
                   for line in abbrevs}
    return abbrevs


def fuzzymatch(name, choices, algo, minm=0):
    """Return best match to name from choices.

    Args
    --------------------------------
    Name: str, String to match
    Choices: List of strings to compare to
    algo: Callable that returns a float between 0 and 100 represnsenting the
        match score (eg. fuzzywuzzy functions)
    minm: The minimum match score that is considered a positive match

    Returns
    --------------------------------
    The string in choices with the highest match score, if score >= minm,
    else None.

    """

    scores = [(algo(name, choice), choice) for choice in choices]
    scores.sort()
    bestscore, bestchoice = scores[0]
    if bestscore >= minm:
        return bestchoice
    else:
        return None


def main():

    def argint_0_100(arg):
        """Validate input is a float between 0 and 1"""
        try:
            if arg >= 0 and arg <= 100:
                return int(arg)
        except:
            pass
        raise ArgumentTypeError("SCORE should be bewteen 0 and 100")

    parser = ArgumentParser()
    parser.add_argument("target", help="The bib file to abbreviate.")
    parser.add_argument(
        "-o",
        "--output",
        help="The output file name.  If missing, output will be sent to stdout.")
    parser.add_argument(
        "-r",
        "--reverse",
        help="Reverse the process and unabbreviate journal names.",
        action="store_true")
    parser.add_argument(
        "-a",
        "--abbreviations",
        help="Path to a file of abbreviations in the form (one per line): Journal of Biological Science = J. Sci. Biol.")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "-m",
        "--match-algorithm",
        help="""Matching algorithm selection for journal names. This should
            be "exact" (default) or a function name from fuzzywuzzy.fuzz""",
        default='exact',
        metavar='ALGO',
        choices=('exact', 'ratio', 'partial_ratio',
                 'token_sort_ratio', 'token_set_ratio'
                 )
        )
    parser.add_argument(
        '-s',
        '--min-match',
        help="int between 0 and 100: Minimum match score value to be\
              considered a match (applied to fuzzy matching only)",
        default=80,
        metavar='SCORE',
        type=argint_0_100,
        )

    args = parser.parse_args()

    level = logging.WARNING if not args.verbose else logging.INFO
    logger.setLevel(level)

    input = open(args.target, "r")
    output = open(args.output, "w") if args.output else sys.stdout

    refs_bp = BibTexParser(
        input.read(), customization=homogeneize_latex_encoding)
    refs = refs_bp.get_entry_dict()
    abbrevs = load_abbrevs(
        determine_path() +
        "/journal_files/journal_abbreviations_general.txt",
        reverse=args.reverse)

    # Assume that if it has a journal key, then it needs abbreviating.  I'm doing this
    # instead of testing for type==article in case I've forgotten about a case where
    # type != article but there's a journal field.
    # Also, journal names with one word ('Nature') don't require
    # abbreviation.
    refs = {key: ref for key, ref in refs.items() if 'journal' in ref}
    refs = {key: ref for key, ref in refs.items()
            if len(ref['journal'].split(' ')) > 1}

    for ref in refs:
        journal = refs[ref]['journal'].lower()

        # Handle any difficult characters.  TODO: check that this list
        # is complete.
        journal_clean = re.sub('[{}]', '', journal)

        # Journal name matching
        if args.match_algorithm == 'exact':
            journal_match = journal_clean
        else:
            algfun = getattr(fuzz, args.match_algorithm)
            journal_match = fuzzymatch(journal_clean, abbrevs.keys(),
                                       algfun, args.min_match)

        try:
            refs[ref]['journal'] = abbrevs[journal_match]
            logger.info('%s replaced with %s for key %s' %
                        (journal, abbrevs[journal_clean], ref))
        except KeyError:
            logger.error('%s not found in abbreviations!' %
                         (journal_clean))

    output_bib = to_bibtex(refs_bp)
    output.write(output_bib)

if __name__ == "__main__":
    main()
