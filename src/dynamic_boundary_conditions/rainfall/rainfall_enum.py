# -*- coding: utf-8 -*-
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

"""
Enum(s) used in the rainfall module.
"""

from enum import StrEnum


class HyetoMethod(StrEnum):
    """
    Enum class representing different hyetograph methods.

    Attributes
    ----------
    ALT_BLOCK : str
        Alternating Block Method.
    CHICAGO : str
        Chicago Method.
    """
    ALT_BLOCK = "alt_block"
    CHICAGO = "chicago"


class RainInputType(StrEnum):
    """
    Enum class representing different types of rain input used in the BG-Flood Model.

    Attributes
    ----------
    UNIFORM : str
        Spatially uniform rain input.
    VARYING : str
        Spatially varying rain input.
    """
    UNIFORM = "uniform"
    VARYING = "varying"
