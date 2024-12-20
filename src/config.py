# Copyright © 2021-2024 Geospatial Research Institute Toi Hangarau
# LICENSE: https://github.com/GeospatialResearch/Digital-Twins/blob/master/LICENSE
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
from typing import Type, TypeVar

from dotenv import load_dotenv

# Generic type, used for static type checking
T = TypeVar("T", str, bool, int, float)

load_dotenv()
load_dotenv("api_keys.env")


def get_env_variable(var_name: str,
                     default: T = None, allow_empty: bool = False, cast_to: Type[T] = str) -> T:
    """
    Reads an environment variable, with settings to allow defaults, empty values, and type casting
    To read a boolean EXAMPLE_ENV_VAR=False use get_env_variable("EXAMPLE_ENV_VAR", cast_to=bool)

    Parameters
    ----------
    var_name : str
        The name of the environment variable to retrieve.
    default : T = None
        Default return value if the environment variable does not exist. Doesn't override empty string vars.
    allow_empty : bool
        If False then a KeyError will be raised if the environment variable is empty.
    cast_to : Type[T]
        The type to cast to e.g. str, int, or bool

    Returns
    -------
    The environment variable, or default if it does not exist, as type T.

    Raises
    ------
    KeyError
        If allow_empty is False and the environment variable is empty string or None
    ValueError
        If cast_to is not compatible with the value stored.
    """
    env_var = os.getenv(var_name, default)
    if not allow_empty and env_var in (None, ""):
        raise KeyError(f"Environment variable {var_name} not set, and allow_empty is False")
    if isinstance(env_var, cast_to):
        return env_var
    # noinspection PyTypeChecker
    return _cast_str(env_var, cast_to)


def _cast_str(str_to_cast: str, cast_to: Type[T]) -> T:
    """
    Takes a string and casts it to necessary primitive builtin types. Tested with int, float, and bool.
    For bool, this detects if the value is in the case-insensitive sets {"True", "T", "1"} or {"False", "F", "0"}
    and raises a ValueError if not. For example _cast_str("False", bool) -> False

    Parameters
    ----------
    str_to_cast : str
        The string that is going to be casted to the type
    cast_to : Type[T]
        The type to cast to e.g. bool

    Returns
    -------
    The string casted to type T defined by cast_to.

    Raises
    ------
    ValueError if [cast_to] is not compatible with the value stored.
    """
    # Special cases i.e. casts that aren't of the form int("7") -> 7
    if cast_to == bool:
        # For bool we have the problem where bool("False") == True but we want this function to return False
        truth_values = {"true", "t", "1"}
        false_values = {"false", "f", "0", ""}
        if str_to_cast is None or str_to_cast.lower() in false_values:
            return False
        elif str_to_cast.lower() in truth_values:
            return True
        raise ValueError(f"{str_to_cast} being casted to bool but is not in {truth_values} or {false_values}")
    # General case
    return cast_to(str_to_cast)
