
import json
import urllib.request
import urllib.error
from urllib.parse import quote

from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version


PYTHON_VERSION = Version("3.11")
REQUIREMENTS_FILE = "requirements.txt"


def get_release_info(package, version):
    """Fetch information about an exact package release from PyPI."""

    url = (
        f"https://pypi.org/pypi/"
        f"{quote(package, safe='')}/{quote(version, safe='')}/json"
    )

    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            data = json.load(response)

        return data["info"].get("requires_python"), None

    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None, "not_found"

        return None, f"HTTP error {error.code}"

    except (urllib.error.URLError, TimeoutError) as error:
        return None, f"Network error: {error}"

    except (json.JSONDecodeError, KeyError) as error:
        return None, f"Invalid PyPI response: {error}"


def get_minimum_python(requires_python):
    """
    Extract the strongest lower bound from Requires-Python.
    Returns (minimum version, operator).
    """

    specifiers = SpecifierSet(requires_python)

    lower_bounds = []

    for spec in specifiers:
        if spec.operator in (">=", ">", "~="):
            lower_bounds.append(
                (Version(spec.version), spec.operator)
            )

        elif spec.operator == "==" and "*" not in spec.version:
            lower_bounds.append(
                (Version(spec.version), "==")
            )

    if not lower_bounds:
        return None

    return max(lower_bounds, key=lambda item: item[0])


def check_requirements():
    with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as file:
        lines = file.readlines()

    not_found = []
    incompatible = []
    network_errors = []
    invalid_lines = []

    highest_requirement = None

    for line_number, line in enumerate(lines, start=1):

        line = line.strip()

        # Ignore blank lines and comments.
        if not line or line.startswith("#"):
            continue

        try:
            requirement = Requirement(line)

            package = requirement.name

            # We expect exact version pins such as package==1.2.3
            pins = [
                spec for spec in requirement.specifier
                if spec.operator == "=="
                and "*" not in spec.version
            ]

            if len(pins) != 1:
                raise ValueError("Expected an exact == version pin")

            version = pins[0].version

        except Exception as error:
            invalid_lines.append((line_number, line, str(error)))
            continue

        requires_python, error = get_release_info(package, version)

        # Package or pinned release does not exist.
        if error == "not_found":
            not_found.append(f"{package}=={version}")
            continue

        # Do not mistake network errors for missing packages.
        if error:
            network_errors.append(
                f"{package}=={version}: {error}"
            )
            continue

        # No Requires-Python means compatible, as requested.
        if not requires_python:
            continue

        try:
            specifiers = SpecifierSet(requires_python)

            # Check whether Python 3.11 satisfies the constraint.
            if not specifiers.contains(PYTHON_VERSION, prereleases=True):
                incompatible.append(
                    f"{package}=={version} "
                    f"(Requires-Python: {requires_python})"
                )

            # Find the release with the highest minimum Python version.
            minimum = get_minimum_python(requires_python)

            if minimum is not None:
                minimum_version, operator = minimum

                if (
                    highest_requirement is None
                    or minimum_version > highest_requirement[0]
                ):
                    highest_requirement = (
                        minimum_version,
                        package,
                        version,
                        operator
                    )

        except Exception as error:
            invalid_lines.append(
                (line_number, line, f"Invalid Requires-Python: {error}")
            )

    # Print results.
    print("\n========== PyPI DEPENDENCY REPORT ==========\n")

    print(f"Dependencies checked: {len(lines)}")

    print("\nNot found on PyPI:")
    if not_found:
        for item in not_found:
            print(f"  - {item}")
    else:
        print("  None")

    print("\nIncompatible with Python 3.11:")
    if incompatible:
        for item in incompatible:
            print(f"  - {item}")
    else:
        print("  None")

    print("\nHighest requirement:")
    if highest_requirement:
        minimum, package, version, operator = highest_requirement
        print(
            f"  {package}=={version}"
            f"({operator}{minimum})"
        )
    else:
        print("  No minimum Python requirement found.")

    if invalid_lines:
        print("\nInvalid requirements:")
        for number, line, reason in invalid_lines:
            print(f"  Line {number}: {line} ({reason})")

    if network_errors:
        print("\nCould not check (network/API errors):")
        for item in network_errors:
            print(f"  - {item}")

    print("\n============================================")


if __name__ == "__main__":
    check_requirements()
