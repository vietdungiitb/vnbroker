import warnings
import requests
from packaging import version
from importlib.metadata import version as get_version
import sys
import os
import re
import time

# Try to import IPython for Jupyter notebook/Google Colab support
try:
    from IPython.display import display, Markdown
    ipython_available = True
except ImportError:
    ipython_available = False

# Import environment utilities
from vnstock.core.utils.env import (
    detect_venv,
    get_python_executable,
    get_python_version_string,
)

# Import version requirements and notices from config
try:
    from vnstock.config import (
        VERSION_REQUIREMENTS,
        VERSION_NOTICES,
        PYTHON_VERSION_SUPPORT,
    )
except ImportError:
    # Fallback if constants not available
    VERSION_REQUIREMENTS = {}
    VERSION_NOTICES = {}
    PYTHON_VERSION_SUPPORT = {}


def detect_environment():
    """
    Detects the running environment (Jupyter, Google Colab, etc.) and returns a string identifier.
    """
    if ipython_available:
        try:
            from IPython import get_ipython
            if 'IPKernelApp' not in get_ipython().config:
                if sys.stdout.isatty():
                    return "Terminal"
                else:
                    return "Other"  # Non-interactive environment (e.g., script executed from an IDE)
            else:
                if 'google.colab' in sys.modules:
                    return "Google Colab"
                return "Jupyter"
        except (ImportError, AttributeError):
            if sys.stdout.isatty():
                return "Terminal"
            else:
                return "Other"
    else:
        if sys.stdout.isatty():
            return "Terminal"
        else:
            return "Other"


def _check_dependency_compatibility():
    """
    Check if installed dependencies meet the requirements for current vnstock version.
    Returns a tuple: (has_issues, critical_issues, warnings)
    Priority packages are checked and displayed first.
    """
    from packaging.specifiers import SpecifierSet
    
    critical_issues = []
    warnings_list = []
    priority_packages = ["vnii"]  # Always check and display first
    
    try:
        vnstock_version = get_version("vnstock").strip()
        
        # Get requirements for this version
        requirements = VERSION_REQUIREMENTS.get(vnstock_version, {})
        if not requirements:
            return False, [], []
        
        # Check priority packages first
        for package in priority_packages:
            if package not in requirements:
                continue
                
            version_spec = requirements[package]
            try:
                installed_version = get_version(package).strip()
                parsed_installed = version.parse(installed_version)
                
                # Parse version specifier (e.g., ">=2.2.3,<3.0.0")
                try:
                    spec_set = SpecifierSet(version_spec)
                    if parsed_installed not in spec_set:
                        critical_issues.append(
                            f"{package}: {installed_version} (requires {version_spec})"
                        )
                except Exception:
                    # Fallback to simple version comparison
                    parsed_required = version.parse(version_spec.lstrip(">=<!=~"))
                    if parsed_installed < parsed_required:
                        critical_issues.append(
                            f"{package}: {installed_version} (requires {version_spec})"
                        )
            except Exception:
                # Package not installed
                pass
        
        # Check other dependencies
        for package, version_spec in requirements.items():
            if package in priority_packages:
                continue  # Already checked above
                
            try:
                installed_version = get_version(package).strip()
                parsed_installed = version.parse(installed_version)
                
                # Parse version specifier
                try:
                    spec_set = SpecifierSet(version_spec)
                    if parsed_installed not in spec_set:
                        critical_issues.append(
                            f"{package}: {installed_version} (requires {version_spec})"
                        )
                except Exception:
                    # Fallback to simple version comparison
                    parsed_required = version.parse(version_spec.lstrip(">=<!=~"))
                    if parsed_installed < parsed_required:
                        critical_issues.append(
                            f"{package}: {installed_version} (requires {version_spec})"
                        )
            except Exception:
                # Package not installed
                critical_issues.append(
                    f"{package}: not installed (requires {version_spec})"
                )
        
        # Check version-specific notices - but merge with priority package issues
        notices = VERSION_NOTICES.get(vnstock_version, {})
        if notices:
            if notices.get("critical_notices"):
                for notice in notices["critical_notices"]:
                    critical_issues.append(notice)
            if notices.get("warnings"):
                warnings_list.extend(notices["warnings"])
        
        # Check Python version compatibility
        supported_py_versions = PYTHON_VERSION_SUPPORT.get(vnstock_version, [])
        if supported_py_versions:
            current_py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
            if current_py_version not in supported_py_versions:
                warnings_list.append(
                    f"Python {current_py_version} not officially supported (requires {', '.join(supported_py_versions)})"
                )
        
        has_issues = bool(critical_issues or warnings_list)
        return has_issues, critical_issues, warnings_list
        
    except Exception:
        return False, [], []


def _display_message(msg, environment, is_warning=False):
    """
    Display message in appropriate format based on environment.
    """
    if environment in ["Jupyter", "Google Colab"] and ipython_available:
        display(Markdown(msg))
    else:
        warnings.simplefilter("always", UserWarning)
        warnings.warn(
            msg.replace("**", "").replace("`", ""),
            UserWarning,
            stacklevel=3
        )


def _get_github_latest_release(repo_owner, repo_name):
    """
    Get the latest release version from GitHub API.
    
    Args:
        repo_owner: GitHub repository owner (e.g., 'vietdungiitb')
        repo_name: GitHub repository name (e.g., 'vnstock')
    
    Returns:
        Version string from the latest release tag, or None if not found
    """
    try:
        response = requests.get(
            f"https://api.github.com/repos/{repo_owner}/{repo_name}/releases/latest",
            timeout=5
        )
        response.raise_for_status()
        
        release_data = response.json()
        tag_name = release_data.get("tag_name", "").strip()
        
        # Extract version from tag (e.g., "v3.5.0" -> "3.5.0")
        if tag_name:
            version_str = tag_name.lstrip("v")
            return version_str
        
        return None
    except Exception:
        return None


def _check_version_updates():
    """
    Check for newer versions from GitHub repository only.
    Compares installed vs latest release version - only show if update available.
    Uses current Python executable for upgrade suggestions.
    """
    environment = detect_environment()
    
    # Get current Python executable and version info
    venv_info = detect_venv()
    python_exe = venv_info.get("python_exe", sys.executable)
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    venv_type = venv_info.get("type", "system")
    
    # Only check vnstock from GitHub repository
    package = "vnstock"
    github_repo_owner = "vietdungiitb"
    github_repo_name = "vnstock"
    github_repo_url = f"https://github.com/{github_repo_owner}/{github_repo_name}"
    
    try:
        installed_version = get_version(package).strip()
        
        # Get latest version from GitHub
        latest_version = _get_github_latest_release(github_repo_owner, github_repo_name)
        
        if latest_version:
            parsed_installed = version.parse(installed_version)
            parsed_latest = version.parse(latest_version)
            
            if parsed_installed < parsed_latest:
                package_name = package.capitalize()
                release_url = f"{github_repo_url}/releases/tag/v{latest_version}"
                
                # Create environment-aware update command using GitHub URL
                if venv_type == "system":
                    update_cmd = (
                        f"pip install git+{github_repo_url}.git@v{latest_version}#egg={package}"
                    )
                else:
                    # For venv/conda, suggest using python -m pip for clarity
                    update_cmd = (
                        f"{python_exe} -m pip install "
                        f"git+{github_repo_url}.git@v{latest_version}#egg={package}"
                    )
                
                env_info = (
                    f"Python {py_version} ({venv_type})"
                    if venv_type != "system"
                    else f"Python {py_version}"
                )
                
                msg = (
                    f"📦 **{package_name} {latest_version} is available**\n"
                    f"Current: {installed_version} ({env_info})\n"
                    f"Update: `{update_cmd}`\n"
                    f"Release: {release_url}"
                )
                _display_message(msg, environment)
    except (
        requests.exceptions.RequestException,
        ImportError,
        Exception
    ):
        pass


def update_notice(verbose=False):
    """
    Check and display package upgrade notices.
    
    Args:
        verbose: If True, show all notices. Else, show critical only.
    """
    try:
        environment = detect_environment()
        
        # Check dependency compatibility
        has_issues, critical_issues, warnings_list = \
            _check_dependency_compatibility()
        
        if has_issues and critical_issues:
            # Show compact critical issues only
            msg_parts = []
            msg_parts.append("⚠️  Dependency issues detected:")
            for issue in critical_issues[:3]:  # Show max 3 issues
                msg_parts.append(f"  • {issue}")
            
            if len(critical_issues) > 3:
                msg_parts.append(f"  ... and {len(critical_issues) - 3} more")
            
            msg_parts.append(
                "\nFor details:\n"
                "from vnstock.core.utils.upgrade import show_full_notice\n"
                "show_full_notice()"
            )
            msg = "\n".join(msg_parts)
            _display_message(msg, environment, is_warning=True)
        
        # Only check updates if verbose or no critical issues
        if verbose or not critical_issues:
            _check_version_updates()
        
    except Exception:
        # Silently fail - never break user code
        pass
        pass


def show_full_notice():
    """
    Show detailed dependency and update info for current environment.
    Call this manually when you want full diagnostics.
    """
    try:
        environment = detect_environment()
        venv_info = detect_venv()
        py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
        
        # Check dependency compatibility
        has_issues, critical_issues, warnings_list = \
            _check_dependency_compatibility()
        
        if has_issues:
            msg_parts = ["📋 **Full Dependency Report**\n"]
            
            # Show environment info
            if venv_info.get("is_active"):
                vcmd = venv_info.get("type")
                vpath = venv_info.get("path")
                python_exe = venv_info.get("python_exe", sys.executable)
                msg_parts.append(
                    f"**Environment:** {vcmd}\n"
                    f"**Path:** {vpath}\n"
                    f"**Python:** {py_version} at {python_exe}\n"
                )
            else:
                python_exe = venv_info.get("python_exe", sys.executable)
                msg_parts.append(
                    f"**Environment:** System (global)\n"
                    f"**Python:** {py_version} at {python_exe}\n"
                )
            
            if critical_issues:
                msg_parts.append("**❌ Critical Issues:**")
                for issue in critical_issues:
                    msg_parts.append(f"  • {issue}")
                msg_parts.append("")
            
            if warnings_list:
                msg_parts.append("**⚠️  Warnings:**")
                for warning in warnings_list:
                    msg_parts.append(f"  • {warning}")
                msg_parts.append("")
            
            msg_parts.append("**Resolution:**")
            python_exe = venv_info.get("python_exe", sys.executable)
            msg_parts.append(
                f"  {python_exe} -m pip install -r requirements.txt "
                "--upgrade"
            )
            
            msg = "\n".join(msg_parts)
            _display_message(msg, environment, is_warning=True)
        else:
            print("✅ All dependencies are compatible!")
        
        # Show available updates
        print(
            "\n📦 Checking for available updates...\n"
            f"📌 Environment: {venv_info.get('type')} "
            f"(Python {py_version})\n"
            f"📌 Executable: {venv_info.get('python_exe', 'system')}\n"
        )
        _check_version_updates()
        
    except Exception as e:
        print(f"Error showing full notice: {e}")


# Customizing the warnings output format for non-notebook environments


def custom_formatwarning(message, category, filename, lineno, line=None):
    return f"{message}\n"


warnings.formatwarning = custom_formatwarning
