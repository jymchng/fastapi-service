import contextlib
import os
import shutil
from functools import wraps
import pathlib

import nox
import nox.command as nox_command
from nox import session as nox_session
from nox.project import load_toml
from nox.sessions import Session

try:
    import tomli as tomllib

    _ = tomllib
except ImportError:
    pass

TYPE_CHECKING = False
TYPE_EXTENSIONS_IMPORTED = False
if TYPE_CHECKING:
    from typing import (
        Any,
        Callable,
        Dict,
        Literal,
        Optional,
        Sequence,
        TypedDict,
        Union,
        overload,
    )

    try:
        from typing_extensions import NotRequired

        TYPE_EXTENSIONS_IMPORTED = True
    except ImportError:
        pass

if TYPE_EXTENSIONS_IMPORTED and TYPE_CHECKING:
    from nox.sessions import Func
    from typing_extensions import ParamSpec

    P = ParamSpec("P")

    class NoxSessionParams(TypedDict):
        """Type hints for Nox session parameters.

        Attributes:
            func: The function to be executed in the session
            python: Python version(s) to use
            py: Alias for python parameter
            reuse_venv: Whether to reuse the virtual environment
            name: Name of the session
            venv_backend: Backend to use for virtual environment
            venv_params: Additional parameters for virtual environment creation
            tags: Tags associated with the session
            default: Whether this is a default session
            requires: Required dependencies for the session
        """

        func: NotRequired[Optional[Union[Callable[..., Any], "Func"]]]  # type: ignore
        python: NotRequired[Optional["PythonVersion"]]  # type: ignore
        py: NotRequired[Optional["PythonVersion"]]  # type: ignore
        reuse_venv: NotRequired[Optional[bool]]
        name: NotRequired[Optional[str]]
        venv_backend: NotRequired[Optional[Any]]
        venv_params: NotRequired[Sequence[str]]
        tags: NotRequired[Optional[Sequence[str]]]
        default: NotRequired[bool]
        requires: NotRequired[Optional[Sequence[str]]]

    PythonVersion = Literal["3.8", "3.9", "3.10", "3.11", "3.12"]

    class ExtraSessionParams(TypedDict):
        """Type hints for extra session parameters.

        Attributes:
            dependency_group: Group to run the session in
        """

        dependency_group: NotRequired[Optional[str]]
        environment_mapping: NotRequired[Optional[Dict[str, str]]]
        default_posargs: NotRequired[Optional[Sequence[str]]]

    class SessionParams(NoxSessionParams, ExtraSessionParams):
        """Type hints for **all** session parameters."""

    @overload
    def session(
        f: Callable[..., Any],
        /,
        dependency_group: str = None,
        environment_mapping: "Dict[str, str]" = {},
        default_posargs: "Sequence[str]" = (),
        **kwargs: NoxSessionParams,
    ) -> Callable[[], Any]: ...

    @overload
    def session(
        f: None = None,
        /,
        dependency_group: str = None,
        environment_mapping: "Dict[str, str]" = {},
        default_posargs: "Sequence[str]" = (),
        **kwargs: NoxSessionParams,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]: ...


# Fundamental Variables
SRC_DIR_NAME = "src"
MANIFEST_FILENAME = "pyproject.toml"
NOXFILE_NAME = "noxfile"

DIST_DIR_NAME: str = "dist"
BUILD_DIR_NAME: str = "build"
TEST_DIR_NAME: str = "tests"
EXAMPLES_DIR_NAME: str = "examples"

ROOT_DIR: str = os.path.dirname(os.path.abspath(__file__))
PROJECT_MANIFEST = load_toml(MANIFEST_FILENAME)
PROJECT_NAME: str = PROJECT_MANIFEST["project"]["name"]
PROJECT_NAME_NORMALIZED: str = PROJECT_NAME.replace("-", "_").replace(" ", "_")
SRC_DIR_PATH = pathlib.Path(SRC_DIR_NAME)
NOXFILE_WITH_EXT_NAME = f"{NOXFILE_NAME}.py"

_PROJECT_CODES_DIR: str = os.path.join(SRC_DIR_NAME, PROJECT_NAME_NORMALIZED)
PROJECT_CODES_DIR: str = (
    _PROJECT_CODES_DIR if os.path.exists(_PROJECT_CODES_DIR) else "."
)
DIST_DIR: str = os.path.join(ROOT_DIR, DIST_DIR_NAME)
BUILD_DIR: str = os.path.join(ROOT_DIR, BUILD_DIR_NAME)
TEST_DIR: str = os.path.join(ROOT_DIR, TEST_DIR_NAME)
EXAMPLES_DIR: str = os.path.join(ROOT_DIR, EXAMPLES_DIR_NAME)


# Statics
DEFAULT_SESSION_KWARGS: "NoxSessionParams" = {
    "reuse_venv": True,  # probably want to reuse it so that you don't keep recreating it
    "venv_backend": "uv",
}


Session.log(
    object.__new__(Session),
    {
        "FUNDAMENTAL VARIABLES": {
            "PROJECT_NAME": PROJECT_NAME,
            "PROJECT_NAME_NORMALIZED": PROJECT_NAME_NORMALIZED,
            "PROJECT_CODES_DIR": PROJECT_CODES_DIR,
            "DIST_DIR": DIST_DIR,
            "BUILD_DIR": BUILD_DIR,
            "TEST_DIR": TEST_DIR,
            "EXAMPLES_DIR": EXAMPLES_DIR,
        }
    },
)


def uv_install_group_dependencies(session: Session, dependency_group: str):
    pyproject = nox.project.load_toml(MANIFEST_FILENAME)
    dependencies = nox.project.dependency_groups(pyproject, dependency_group)
    session.install(*dependencies)
    session.log(f"Installed dependencies: {dependencies} for {dependency_group}")


class AlteredSession(Session):
    __slots__ = (
        "session",
        "dependency_group",
        "environment_mapping",
        "default_posargs",
    )

    def __init__(
        self,
        session: Session,
        dependency_group: str,
        environment_mapping: "Dict[str, str]",
        default_posargs: "Sequence[str]",
    ):
        super().__init__(session._runner)
        self.dependency_group = dependency_group
        self.environment_mapping = environment_mapping
        self.default_posargs = default_posargs
        self.session = session

    def run(self, *args, **kwargs):
        if self.dependency_group is not None:
            uv_install_group_dependencies(self, self.dependency_group)
        if self.session.posargs is not None:
            args = (*args, *(self.session.posargs or self.default_posargs))
        env: "Dict[str, str]" = kwargs.pop("env", {})
        env.update(self.environment_mapping)
        kwargs["env"] = env
        return self.session.run(*args, **kwargs)


def session(
    f: "Optional[Callable[..., Any]]" = None,
    /,
    dependency_group: "Optional[str]" = None,
    environment_mapping: "Dict[str, str]" = {},
    default_posargs: "Sequence[str]" = (),
    **kwargs: "NoxSessionParams",
) -> "Callable[..., Any]":
    if f is None:
        return lambda f: session(
            f,
            dependency_group=dependency_group,
            environment_mapping=environment_mapping,
            default_posargs=default_posargs,
            **kwargs,
        )
    session_name = kwargs.get("name", f.__name__.replace("_", "-"))
    nox_session_kwargs = {
        **DEFAULT_SESSION_KWARGS,
        "name": session_name,
        **kwargs,
    }

    @wraps(f)
    def wrapper(session: Session, *args, **kwargs):
        altered_session = AlteredSession(
            session, dependency_group, environment_mapping, default_posargs
        )
        return f(altered_session, *args, **kwargs)

    return nox_session(wrapper, **nox_session_kwargs)


@session(
    dependency_group="test",
    default_posargs=[
        TEST_DIR,
        "-s",
        "-vv",
    ],
)
def test(session: AlteredSession):
    command = [
        shutil.which("uv"),
        "run",
        "python",
        "-m",
        "pytest",
    ]
    if "--build" in session.posargs:
        session.posargs.remove("--build")
        with alter_session(session, dependency_group="build"):
            build(session)
    session.run(*command)


@contextlib.contextmanager
def alter_session(
    session: AlteredSession,
    dependency_group: str = None,
    environment_mapping: "Dict[str, str]" = {},
    default_posargs: "Sequence[str]" = (),
    **kwargs: "NoxSessionParams",
):
    old_dependency_group = session.dependency_group
    old_environment_mapping = session.environment_mapping
    old_default_posargs = session.default_posargs
    old_kwargs = {}
    for key, value in kwargs.items():
        old_kwargs[key] = getattr(session, key)

    session.dependency_group = dependency_group
    session.environment_mapping = environment_mapping
    session.default_posargs = default_posargs
    for key, value in kwargs.items():
        setattr(session, key, value)
    yield session

    session.dependency_group = old_dependency_group
    session.environment_mapping = old_environment_mapping
    session.default_posargs = old_default_posargs
    for key, value in old_kwargs.items():
        setattr(session, key, value)


@session(
    dependency_group="dev",
)
def clean(session: Session):
    session.run("rm", "-rf", BUILD_DIR, DIST_DIR, "*.egg-info")

    import glob
    import os
    import shutil
    from pathlib import Path

    extensions_patterns = [
        "**/*.cpython-*.so",
        "**/*.abi3.so",
        "**/*.so",
        "**/*.pyd",
        f"{PROJECT_CODES_DIR}/**/*.so",
        f"{PROJECT_CODES_DIR}/**/*.pyd",
        f"{BUILD_DIR}/**/*.so",
        f"{BUILD_DIR}/**/*.pyd",
    ]

    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)

    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR)

    for pattern in extensions_patterns:
        for file in glob.glob(pattern, recursive=True):
            try:
                os.remove(file)
                session.log(f"Removed: {file}")
            except OSError as e:
                session.log(f"Error removing {file}: {e}")

    for root, dirs, files in os.walk(ROOT_DIR):
        for dir in dirs:
            if dir == "__pycache__":
                cache_dir = Path(root) / dir
                try:
                    shutil.rmtree(cache_dir)
                    session.log(f"Removed cache directory: {cache_dir}")
                except OSError as e:
                    session.log(f"Error removing {cache_dir}: {e}")

        for file in files:
            if file.endswith(".pyc"):
                pyc_file = Path(root) / file
                try:
                    os.remove(pyc_file)
                    session.log(f"Removed: {pyc_file}")
                except OSError as e:
                    session.log(f"Error removing {pyc_file}: {e}")


@session(
    dependency_group="examples",
)
def fastapi_auth(session: Session):
    test_development(session)
    with alter_session(session, environment_mapping={"ENVIRONMENT_KEY": "staging"}):
        test_staging(session)
    with alter_session(session, environment_mapping={"ENVIRONMENT_KEY": "production"}):
        test_production(session)
    test_development(session)


@session(
    dependency_group="examples",
    default_posargs=[
        f"{EXAMPLES_DIR}/scratchpad.py",
    ],
)
def scratchpad(session: Session):
    command = [
        shutil.which("uv"),
        "run",
        "--group",
        "examples",
        "python",
    ]
    session.run(*command)


@session(
    dependency_group="examples",
    environment_mapping={"ENVIRONMENT_KEY": "staging"},
    default_posargs=[f"{EXAMPLES_DIR}/fastapi_auth_staging.py", "-s", "-vv"],
)
def test_staging(session: Session):
    session.run(
        "uv",
        "run",
        "--group",
        "examples",
        "python",
        "-m",
        "pytest",
    )


@session(
    dependency_group="examples",
    environment_mapping={"ENVIRONMENT_KEY": "production"},
    default_posargs=[f"{EXAMPLES_DIR}/fastapi_auth_prod.py", "-s", "-vv"],
)
def test_production(session: Session):
    session.run(
        "uv",
        "run",
        "--group",
        "examples",
        "python",
        "-m",
        "pytest",
    )


@session(
    dependency_group="examples",
    environment_mapping={"ENVIRONMENT_KEY": "development"},
    default_posargs=[f"{EXAMPLES_DIR}/fastapi_auth_dev.py", "-s", "-vv"],
)
def test_development(session: Session):
    session.run(
        "uv",
        "run",
        "--group",
        "examples",
        "python",
        "-m",
        "pytest",
    )


@session(
    dependency_group="dev",
    default_posargs=[
        pathlib.Path(PROJECT_CODES_DIR),
        pathlib.Path(TEST_DIR),
        pathlib.Path(NOXFILE_WITH_EXT_NAME),
    ],
)
def format(session: Session):
    import glob
    import os

    format_dir = pathlib.Path(PROJECT_CODES_DIR)

    session.log(f"Using {format_dir} as the directory for formatting")

    session.run("uv", "tool", "run", "ruff", "format")

    c_files_path = format_dir
    if not os.path.exists(c_files_path):
        session.log(f"Directory {c_files_path} does not exist, skipping clang-format")
        return

    c_files = glob.glob(f"{c_files_path}/*.c", recursive=True)
    if not c_files:
        session.log(f"No C files found in {c_files_path}, skipping clang-format")
        return
    nox_command.run(("uv", "tool", "run", "clang-format", "-i", *c_files))


@session(dependency_group="dev")
def check(session: Session):
    check_ruff(session)
    check_mypy(session)
    check_pyright(session)


@session(dependency_group="dev", default_posargs=["check", ".", "--fix"])
def check_ruff(session: Session):
    session.run("uv", "tool", "run", "ruff")


@session(
    dependency_group="dev",
    default_posargs=[SRC_DIR_NAME, "--rcfile", MANIFEST_FILENAME],
)
def lint(session: Session):
    session.run("uv", "tool", "run", "pylint")


@session(dependency_group="dev")
def build(session: Session):
    session.run("uv", "build")


@session(dependency_group="test", default_posargs=[f"{TEST_DIR}/benchmark.py", "-v"])
def benchmark(session: Session):
    session.run(
        "uv",
        "run",
        "--group",
        "test",
        "python",
        "-m",
        "pytest",
    )


@session(dependency_group="dev")
def list_dist_files(session: Session):
    """List all files packaged in the latest distribution."""
    import glob
    import os
    import zipfile
    from pathlib import Path

    wheel_files = sorted(
        glob.glob(f"{DIST_DIR}/*.whl"), key=os.path.getmtime, reverse=True
    )
    tarball_files = sorted(
        glob.glob(f"{DIST_DIR}/*.tar.gz"), key=os.path.getmtime, reverse=True
    )

    if not wheel_files and not tarball_files:
        session.error("No distribution files found in dist/ directory")
        return

    if wheel_files:
        latest_wheel = wheel_files[0]
        session.log(f"Examining contents of {latest_wheel}")

        with zipfile.ZipFile(latest_wheel, "r") as wheel:
            file_list = wheel.namelist()

            session.log(f"Contents of {Path(latest_wheel).name}:")
            for file in sorted(file_list):
                session.log(f"  - {file}")

            session.log(f"Total files in wheel: {len(file_list)}")

    if tarball_files:
        latest_tarball = tarball_files[0]
        session.log(f"Examining contents of {latest_tarball}")

        import tarfile

        with tarfile.open(latest_tarball, "r:gz") as tar:
            file_list = tar.getnames()

            session.log(f"Contents of {Path(latest_tarball).name}:")
            for file in sorted(file_list):
                session.log(f"  - {file}")

            session.log(f"Total files in tarball: {len(file_list)}")


@session(
    dependency_group="dev", default_posargs=[PROJECT_CODES_DIR, "--check-untyped-defs"]
)
def check_mypy(session: Session):
    session.run("uv", "tool", "run", "mypy")


@session(dependency_group="dev", default_posargs=[SRC_DIR_NAME])
def check_pyright(session: Session):
    session.run("uv", "tool", "run", "pyright")


@session(dependency_group="dev")
def dev(session: Session):
    clean(session)
    format(session)
    check(session)
    build(session)
    list_dist_files(session)
    test(session)


@session(dependency_group="dev")
def ci(session: Session):
    list_dist_files(session)
    test(session)


@session(reuse_venv=False)
def test_client_install_run(session: Session):
    with alter_session(session, dependency_group="dev"):
        clean(session)
        build(session)
    with alter_session(session, dependency_group="dev"):
        list_dist_files(session)
    session.run("pip", "uninstall", f"{PROJECT_NAME}", "-y")
    import glob
    import re

    from packaging import version

    tarball_files = glob.glob(f"{DIST_DIR}/{PROJECT_NAME_NORMALIZED}-*.tar.gz")

    if not tarball_files:
        session.error("No tarball files found in dist/ directory")

    version_pattern = re.compile(
        rf"{PROJECT_NAME_NORMALIZED}-([0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?).tar.gz"
    )

    versioned_files = []
    for file_path in tarball_files:
        match = version_pattern.search(file_path)
        if match:
            ver_str = match.group(1)
            versioned_files.append((file_path, version.parse(ver_str)))

    if not versioned_files:
        session.error("Could not extract version information from tarball files")

    latest_tarball = sorted(versioned_files, key=lambda x: x[1], reverse=True)[0][0]
    session.log(f"Installing latest version: {latest_tarball}")
    session.run(
        "uv",
        "run",
        "pip",
        "install",
        latest_tarball,
    )
    session.run(
        "uv",
        "run",
        "python",
        "-c",
        f"from {PROJECT_NAME_NORMALIZED} import Shield, __version__; print(f'Shield imported, version: {{__version__}}')",
    )
    session.run("uv", "run", "pip", "uninstall", f"{PROJECT_NAME}", "-y")

    with alter_session(session, dependency_group="dev"):
        test(session)


@session
def run_examples(session: Session):
    import glob

    if session.posargs:
        examples_scripts = glob.glob(f"{EXAMPLES_DIR}/{session.posargs[0]}")
    else:
        examples_scripts = glob.glob(f"{EXAMPLES_DIR}/*.py")
    for script in examples_scripts:
        session.run("uv", "run", script)


@session(dependency_group="dev", default_posargs=[PROJECT_CODES_DIR])
def no_print(session: Session):
    output = session.run(
        "grep",
        "-rn",
        "print",
        silent=True,
        success_codes=[1],
    )
    if output:
        session.error("Found print statements in the code")
        raise SystemExit(1)


@session(reuse_venv=False)
def test_all_vers(session: Session):
    session.run("bash", "tests/build_test_pyvers_docker_images.sh", external=True)


@session(dependency_group="dev")
def version_sync(session: Session):
    """Sync version between pyproject.toml and __init__.py."""
    import re

    with open("pyproject.toml", "r") as f:
        pyproject_content = f.read()

    version_match = re.search(r'version = "([^"]+)"', pyproject_content)
    if not version_match:
        session.error("Could not find version in pyproject.toml")

    pyproject_version = version_match.group(1)
    session.log(f"Found version in pyproject.toml: {pyproject_version}")

    init_file = f"{PROJECT_CODES_DIR}/__init__.py"
    with open(init_file, "r") as f:
        init_content = f.read()

    updated_content = re.sub(
        r'__version__ = "[^"]+"', f'__version__ = "{pyproject_version}"', init_content
    )

    with open(init_file, "w") as f:
        f.write(updated_content)

    session.log(f"SUCCESS: Synced version to {pyproject_version} in {init_file}")


@session(dependency_group="dev")
def bump_version(session: Session):
    """Bump version (minor by default, or specify: patch, minor, major)."""
    import re

    bump_type = "patch"
    if session.posargs:
        bump_type = session.posargs[0].lower()
        if bump_type not in ["patch", "minor", "major"]:
            session.error(
                f"Invalid bump type: {bump_type}. Use: patch, minor, or major"
            )

    session.log(f"Bumping {bump_type} version...")

    with open("pyproject.toml", "r") as f:
        content = f.read()

    version_match = re.search(r'version = "([^"]+)"', content)
    if not version_match:
        session.error("Could not find version in pyproject.toml")

    current_version = version_match.group(1)
    session.log(f"Current version: {current_version}")

    version_parts = current_version.split(".")
    if len(version_parts) != 3:
        session.error(f"Invalid version format: {current_version}. Expected: X.Y.Z")

    major, minor, patch = map(int, version_parts)

    if bump_type == "major":
        major += 1
        minor = 0
        patch = 0
    elif bump_type == "minor":
        minor += 1
        patch = 0
    elif bump_type == "patch":
        patch += 1

    new_version = f"{major}.{minor}.{patch}"
    session.log(f"New version: {new_version}")

    updated_content = re.sub(
        r'version = "[^"]+"', f'version = "{new_version}"', content
    )

    with open("pyproject.toml", "w") as f:
        f.write(updated_content)

    session.log(f"SUCCESS: Updated pyproject.toml to version {new_version}")

    version_sync(session)

    return new_version


@session(dependency_group="dev")
def git_check(session: Session):
    """Check git status and ensure clean working directory."""
    result = session.run(
        "git",
        "status",
        "--porcelain",
        silent=True,
        external=True,
        success_codes=[0, 128],
    )
    if result is False:
        session.error("Not a git repository")

    result = session.run("git", "status", "--porcelain", silent=True)
    if result and result.strip():
        session.error("Working directory is not clean. Commit or stash changes first.")

    result = session.run("git", "branch", "--show-current", silent=True)
    current_branch = result.strip() if result else ""

    if current_branch not in ["main", "master"]:
        session.log(f"WARNING: Not on main/master branch (current: {current_branch})")

    session.log("SUCCESS: Git repository is clean and ready")


@session(dependency_group="dev")
def release_check(session: Session):
    """Pre-release validation checklist."""
    session.log("[CHECK] Running pre-release checks...")

    git_check(session)

    clean(session)
    format(session)
    check(session)
    test(session)

    build(session)
    list_dist_files(session)

    test_install(session)

    session.log("SUCCESS: All pre-release checks passed!")


@session(dependency_group="dev")
def release(session: Session):
    """Create a release with version bump, git tag, and build."""
    bump_type = "minor"
    if session.posargs:
        bump_type = session.posargs[0].lower()

    session.log(f"[RELEASE] Starting release process (bump: {bump_type})...")

    release_check(session)

    new_version = bump_version(session)

    session.run("git", "add", "pyproject.toml", f"{PROJECT_CODES_DIR}/__init__.py")
    session.run("git", "commit", "-m", f"chore: bump version to {new_version}")

    tag_name = f"v{new_version}"
    session.run("git", "tag", "-a", tag_name, "-m", f"Release {new_version}")

    session.log(f"SUCCESS: Created git tag: {tag_name}")

    clean(session)
    build(session)

    session.log(f"SUCCESS: Release {new_version} ready!")
    session.log("Next steps:")
    session.log("  1. Push changes: git push origin main")
    session.log(f"  2. Push tag: git push origin {tag_name}")
    session.log("  3. Publish to TestPyPI: nox -s publish-test")
    session.log("  4. Publish to PyPI: nox -s publish")


@session(dependency_group="dev")
def publish_test(session: Session):
    """Publish to TestPyPI using uv."""
    session.log("[PUBLISH] Publishing to TestPyPI...")

    if not os.path.exists(DIST_DIR) or not os.listdir(DIST_DIR):
        session.log("No distribution files found, building...")
        build(session)

    session.run(
        "uv", "publish", "--publish-url", "https://test.pypi.org/legacy/", "dist/*"
    )
    session.log("SUCCESS: Published to TestPyPI")


@session(dependency_group="dev")
def publish(session: Session):
    """Publish to PyPI using uv."""
    session.log("[PUBLISH] Publishing to PyPI...")

    if not os.path.exists(DIST_DIR) or not os.listdir(DIST_DIR):
        session.log("No distribution files found, building...")
        build(session)

    response = input(
        "Are you sure you want to publish to PyPI? This cannot be undone. (y/N): "
    )
    if response.lower() != "y":
        session.error("Publication cancelled")

    session.run("twine", "upload", "dist/*")
    session.log("SUCCESS: Published to PyPI!")


@session(dependency_group="dev")
def hotfix(session: Session):
    """Create a hotfix release (patch version bump)."""
    session.log("[HOTFIX] Creating hotfix release...")

    session.posargs = ["patch"]
    release(session)


@session(dependency_group="dev")
def release_info(session: Session):
    """Show current release information."""
    import re

    with open("pyproject.toml", "r") as f:
        content = f.read()

    version_match = re.search(r'version = "([^"]+)"', content)
    current_version = version_match.group(1) if version_match else "unknown"

    try:
        current_branch = session.run(
            "git", "branch", "--show-current", silent=True
        ).strip()
        last_tag = session.run(
            "git",
            "describe",
            "--tags",
            "--abbrev=0",
            silent=True,
            success_codes=[0, 128],
        ).strip()
        commits_since_tag = session.run(
            "git",
            "rev-list",
            f"{last_tag}..HEAD",
            "--count",
            silent=True,
            success_codes=[0, 128],
        ).strip()
    except Exception:
        current_branch = "unknown"
        last_tag = "none"
        commits_since_tag = "unknown"

    session.log("[INFO] Release Information:")
    session.log(f"  Current version: {current_version}")
    session.log(f"  Current branch: {current_branch}")
    session.log(f"  Last tag: {last_tag}")
    session.log(f"  Commits since tag: {commits_since_tag}")

    version_parts = current_version.split(".")
    if len(version_parts) == 3:
        major, minor, patch = map(int, version_parts)
        session.log("  Next versions would be:")
        session.log(f"    Patch: {major}.{minor}.{patch + 1}")
        session.log(f"    Minor: {major}.{minor + 1}.0")
        session.log(f"    Major: {major + 1}.0.0")


@session(dependency_group="dev", reuse_venv=True)
def test_install(session: Session):
    """Test package installation in a completely fresh environment."""
    session.log("[TEST] Testing package installation in fresh environment...")

    session.log("[CLEAN] Cleaning up any existing installations...")
    session.run("uv", "pip", "uninstall", PROJECT_NAME, success_codes=[0, 1])

    if not os.path.exists(DIST_DIR) or not os.listdir(DIST_DIR):
        session.log("No distribution files found, building first...")
        build(session)

    import glob
    from pathlib import Path

    wheel_files = sorted(
        glob.glob(f"{DIST_DIR}/*.whl"), key=os.path.getmtime, reverse=True
    )
    tarball_files = sorted(
        glob.glob(f"{DIST_DIR}/*.tar.gz"), key=os.path.getmtime, reverse=True
    )

    if not wheel_files and not tarball_files:
        session.error("No distribution files found to test")

    test_files = []
    if wheel_files:
        test_files.append(("wheel", wheel_files[0]))
    if tarball_files:
        test_files.append(("tarball", tarball_files[0]))

    for dist_type, dist_file in test_files:
        session.log(f"[PACKAGE] Testing {dist_type}: {Path(dist_file).name}")

        session.run("uv", "pip", "uninstall", PROJECT_NAME, success_codes=[0, 1])

        session.install(dist_file)

        result = session.run(
            "uv", "pip", "show", PROJECT_NAME, silent=True, success_codes=[0, 1]
        )
        if not result:
            session.error(f"Package {PROJECT_NAME} was not installed correctly")

        session.log("[CHECK] Testing basic import...")
        session.run(
            "python",
            "-c",
            f"import {PROJECT_NAME_NORMALIZED}; print('SUCCESS: Successfully imported {PROJECT_NAME_NORMALIZED}')",
        )

        session.log("[CHECK] Testing version access...")
        session.run(
            "python",
            "-c",
            f"from {PROJECT_NAME_NORMALIZED} import __version__; print(f'VERSION: {{__version__}}')",
        )

        session.log("[CHECK] Testing main components...")
        session.run(
            "python",
            "-c",
            f"from {PROJECT_NAME_NORMALIZED} import Shield, ShieldedDepends, shield; print('SUCCESS: All main components imported successfully')",
        )

        session.log("[CHECK] Testing FastAPI integration...")
        fastapi_test = f"""
from fastapi import FastAPI
from {PROJECT_NAME_NORMALIZED} import shield

app = FastAPI()

@shield
def simple_shield():
    return {{"status": "ok"}}

@app.get("/test")
@simple_shield
async def test_endpoint():
    return {{"message": "FastAPI integration works"}}

print("SUCCESS: FastAPI integration test passed")
"""
        session.run("python", "-c", fastapi_test)

        session.run("uv", "pip", "uninstall", PROJECT_NAME, success_codes=[0, 1])
        session.log(
            f"SUCCESS: {dist_type.capitalize()} installation test completed successfully"
        )

    session.log(
        "SUCCESS: All installation tests passed! Package is ready for end users."
    )


@session(dependency_group="dev", reuse_venv=True)
def test_install_from_pypi(session: Session):
    """Test installation from PyPI (or TestPyPI)."""

    session.log("[CLEAN] Cleaning up any existing installations...")
    session.run("uv", "pip", "uninstall", PROJECT_NAME, success_codes=[0, 1])

    pypi_url = "https://test.pypi.org/simple/"
    if session.posargs and session.posargs[0] == "pypi":
        pypi_url = None  # Use default PyPI
        session.log("[PACKAGE] Testing installation from PyPI...")
    else:
        session.log("[PACKAGE] Testing installation from TestPyPI...")

    install_cmd = ["uv", "pip", "install"]
    if pypi_url:
        install_cmd.extend(
            ["-i", pypi_url, "--extra-index-url", "https://pypi.org/simple/"]
        )
    install_cmd.append(PROJECT_NAME)

    try:
        session.run(*install_cmd)
        session.log("SUCCESS: Package installed successfully from PyPI")

        result = session.run(
            "uv", "pip", "show", PROJECT_NAME, silent=True, success_codes=[0, 1]
        )
        if not result:
            session.error(
                f"Package {PROJECT_NAME} was not installed correctly from PyPI"
            )

        session.log("[CHECK] Testing installed package...")
        session.run(
            "python",
            "-c",
            f"import {PROJECT_NAME_NORMALIZED}; print('SUCCESS: Successfully imported {PROJECT_NAME_NORMALIZED}')",
        )
        session.run(
            "python",
            "-c",
            f"from {PROJECT_NAME_NORMALIZED} import __version__; print(f'VERSION: {{__version__}}')",
        )
        session.run(
            "python",
            "-c",
            f"from {PROJECT_NAME_NORMALIZED} import Shield, ShieldedDepends, shield; print('SUCCESS: All main components imported successfully')",
        )

        session.log("SUCCESS: PyPI installation test passed!")

    except Exception as e:
        session.error(f"PyPI installation test failed: {e}")
    finally:
        session.run("uv", "pip", "uninstall", PROJECT_NAME, success_codes=[0, 1])


@session(dependency_group="dev", reuse_venv=True)
def test_install_editable(session: Session):
    """Test editable installation for development."""
    session.log("[TEST] Testing editable installation...")

    session.log("[CLEAN] Cleaning up any existing installations...")
    session.run("uv", "pip", "uninstall", PROJECT_NAME, success_codes=[0, 1])

    session.run("uv", "pip", "install", "-e", ".")

    result = session.run(
        "uv", "pip", "show", PROJECT_NAME, silent=True, success_codes=[0, 1]
    )
    if not result:
        session.error(f"Editable package {PROJECT_NAME} was not installed correctly")

    session.log("[CHECK] Testing editable installation...")
    session.run(
        "python",
        "-c",
        f"import {PROJECT_NAME_NORMALIZED}; print('SUCCESS: Editable installation works')",
    )

    session.run(
        "python",
        "-c",
        f"""
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'src'))
from {PROJECT_NAME_NORMALIZED} import Shield
print('SUCCESS: Can import from source directory')
""",
    )

    session.run(
        "python",
        "-c",
        f"""
import {PROJECT_NAME_NORMALIZED}
import os
module_path = {PROJECT_NAME_NORMALIZED}.__file__
project_src = os.path.join(os.getcwd(), 'src', '{PROJECT_NAME_NORMALIZED}')
if project_src in module_path:
    print('SUCCESS: Package is installed in editable mode')
else:
    print(f'WARNING: Package may not be in editable mode. Module path: {{module_path}}')
""",
    )

    session.log("SUCCESS: Editable installation test passed!")


@session(dependency_group="dev")
def test_install_all(session: Session):
    """Run all installation tests."""
    session.log("[TEST] Running comprehensive installation tests...")

    build(session)

    test_install(session)

    test_install_editable(session)

    session.log("SUCCESS: All installation tests completed successfully!")


@session(dependency_group="docs")
def export_docs_reqs(session: Session):
    session.run(*("uv export --only-group docs -o requirements-docs.txt".split(" ")))


@session(dependency_group="docs")
def build_docs(session: Session):
    session.chdir(ROOT_DIR)
    session.run("uv", "pip", "install", "-e", ".")
    session.run("mkdocs", "build")


@session(dependency_group="docs")
def serve_docs(session: Session):
    session.chdir(ROOT_DIR)
    session.run("uv", "pip", "install", "-e", ".")
    session.run("mkdocs", "serve", "-a", "localhost:8001")


@session(dependency_group="dev")
def revert_release(session: AlteredSession):
    """Revert a release by deleting the git tag locally and remotely, and rolling back the version.

    This function will:
    1. Delete the specified git tag locally and remotely
    2. Decrement the patch version by 1 in pyproject.toml and __init__.py

    Usage: nox -s revert-release -- <tag_name>
    Example: nox -s revert-release -- v1.2.3
    """
    if not session.posargs:
        session.error(
            "Please provide a tag name to revert. Usage: nox -s revert-release -- <tag_name>"
        )
        return

    tag_name = session.posargs[0]

    try:
        session.session.run("git", "tag", "-l", tag_name, external=True, silent=True)
    except Exception:
        session.error(f"Tag '{tag_name}' does not exist locally")
        return

    try:
        session.session.run("git", "diff", "--quiet", external=True, silent=True)
        session.session.run(
            "git", "diff", "--cached", "--quiet", external=True, silent=True
        )
    except Exception:
        session.error(
            "Git repository has uncommitted changes. Please commit or stash them first."
        )
        return

    session.log(f"Reverting release tag: {tag_name}")

    session.log(f"Deleting local tag: {tag_name}")
    session.session.run("git", "tag", "-d", tag_name, external=True)

    session.log(f"Deleting remote tag: {tag_name}")
    session.session.run(
        "git", "push", "origin", f":refs/tags/{tag_name}", external=True
    )

    session.log("Rolling back version numbers...")

    import re
    import pathlib

    pyproject_path = pathlib.Path("pyproject.toml")
    with open(pyproject_path, "r") as f:
        pyproject_content = f.read()

    version_match = re.search(r'version = "(\d+)\.(\d+)\.(\d+)"', pyproject_content)
    if not version_match:
        session.error("Could not find version in pyproject.toml")
        return

    major, minor, patch = map(int, version_match.groups())
    if patch == 0:
        session.error("Cannot decrement patch version below 0")
        return

    new_patch = patch - 1
    new_version = f"{major}.{minor}.{new_patch}"

    new_pyproject_content = re.sub(
        r'version = "\d+\.\d+\.\d+"', f'version = "{new_version}"', pyproject_content
    )

    with open(pyproject_path, "w") as f:
        f.write(new_pyproject_content)

    session.log(f"Updated pyproject.toml version to {new_version}")

    init_path = SRC_DIR_PATH / PROJECT_NAME_NORMALIZED / "__init__.py"
    with open(init_path, "r") as f:
        init_content = f.read()

    new_init_content = re.sub(
        r'__version__ = "\d+\.\d+\.\d+"', f'__version__ = "{new_version}"', init_content
    )

    with open(init_path, "w") as f:
        f.write(new_init_content)

    session.log(f"Updated __init__.py version to {new_version}")

    session.log(
        f"SUCCESS: Tag '{tag_name}' has been deleted locally and remotely, and version rolled back to {new_version}"
    )
