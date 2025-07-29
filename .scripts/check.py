import glob
import json
import os
import sys
import subprocess

import requests
import yaml

# Globals

ASSIGNMENTS     = {}
DREDD_QUIZ_URL  = 'https://dredd.h4x0r.space/quiz/cse-30872-fa24/'
DREDD_CODE_SLUG = 'debug' if bool(os.environ.get('DEBUG', False)) else 'code'
DREDD_CODE_URL  = f'https://leaderboard.williamtheisen.com/code/'

# Utilities

def add_assignment(assignment, path=None):
    if path is None:
        path = assignment

    if assignment.startswith('reading') or assignment.startswith('challenge'):
        ASSIGNMENTS[assignment] = path

def print_results(results, print_status=True):
    for key, value in sorted(results.items()):
        if key in ('score', 'status', 'value'):
            continue

        try:
            print('{:>8} {:.2f}'.format(key.title(), value))
        except ValueError:
            if key in ('stdout', 'diff'):
                print('{:>8}\n{}'.format(key.title(), value))
            else:
                print('{:>8} {}'.format(key.title(), value))

    print('{:>8} {:.2f} / {:.2f}'.format('Score', results.get('score', 0), results.get('value', 0)))
    if print_status:
        print('{:>8} {}'.format('Status', 'Success' if int(results.get('status', 1)) == 0 else 'Failure'))

def read_secret_token():
    """Read the secret token from the secret_token.txt file in the root of the git repository."""
    print('Reading secret token from secret_token.txt')
    try:
        # Get the root directory of the git repository
        git_root = subprocess.check_output(['git', 'rev-parse', '--show-toplevel']).strip().decode('utf-8')
        print(f'Git root: {git_root}')
        secret_token_path = os.path.join(git_root, 'secret_token.txt')
        print(f'Secret token path: {secret_token_path}')
        with open(secret_token_path, 'r') as file:
            return file.read().strip()
    except subprocess.CalledProcessError:
        print('Not a git repository or git command failed.')
        return None
    except FileNotFoundError:
        print('secret_token.txt file not found in the git root directory.')
        return None

# Check Functions

def check_quiz(assignment, path):
    answers = None

    for mod_load, ext in ((json.load, 'json'), (yaml.safe_load, 'yaml')):
        try:
            answers = mod_load(open(os.path.join(path, 'answers.' + ext)))
        except IOError as e:
            pass
        except Exception as e:
            print('Unable to parse answers.{}: {}'.format(ext, e))
            return 1

    if answers is None:
        print('No quiz found (answers.{json,yaml})')
        return 1

    print('Checking {} quiz ...'.format(assignment))
    response = requests.post(DREDD_QUIZ_URL + assignment, data=json.dumps(answers))
    print_results(response.json())
    print()

    return int(response.json().get('status', 1))


def check_code(assignment, path):
    print(f'Checking code for {assignment} in {path}')
    sources = glob.glob(os.path.join(path, 'program.*'))

    if not sources:
        print('No code found (program.*)')
        return 1

    # Read secret token
    secret_token = read_secret_token()
    if not secret_token:
        print('Secret token is missing. Cannot proceed with submission.')
        return 1
    
    result = 1
    for source in sources:
        print('\nChecking {} {} ...'.format(assignment, os.path.basename(source)))
        
        # Add headers to include GitHub username, DREDD_CODE_SLUG, and secret token
        headers = {
            'X-Dredd-Code-Slug': DREDD_CODE_SLUG,
            'X-Submission-Token': secret_token
        }
        
        response = requests.post(
            DREDD_CODE_URL + assignment, 
            files={'source': open(source)},
            headers=headers
        )
        print(response)
        print_results(response.json(), False)

        result = min(result, int(response.json().get('status', 1)))
    return result

def main():
    # Add GitLab/GitHub branch
    for variable in ['CI_BUILD_REF_NAME', 'GITHUB_HEAD_REF']:
        try:
            add_assignment(os.environ[variable])
        except KeyError:
            pass

    # Add local git branch
    try:
        add_assignment(os.popen('git symbolic-ref -q --short HEAD 2> /dev/null').read().strip())
    except OSError:
        pass

    # Add current directory
    add_assignment(os.path.basename(os.path.abspath(os.curdir)), os.curdir)

    # For each assignment, submit quiz answers and program code

    if not ASSIGNMENTS:
        print('Nothing to submit!')
        sys.exit(1)

    exit_code = 0

    for assignment, path in sorted(ASSIGNMENTS.items()):
        if 'reading' in assignment:
            exit_code += check_quiz(assignment, path)
        elif 'challenge' in assignment:
            exit_code += check_code(assignment, path)

    sys.exit(exit_code)

if __name__ == '__main__':
    main()

# vim: set sts=4 sw=4 ts=8 expandtab ft=python:
