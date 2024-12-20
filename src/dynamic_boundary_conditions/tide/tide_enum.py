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
Enum(s) used in the tide_slr module.
"""

from enum import StrEnum


class DatumType(StrEnum):
    """
    Enum class representing different datum types.

    Attributes
    ----------
    LAT : str
        Lowest astronomical tide.
    MSL : str
        Mean sea level.
    """
    LAT = "lat"
    MSL = "msl"


class ApproachType(StrEnum):
    """
    Enum class representing different types of approaches.

    Attributes
    ----------
    KING_TIDE : str
        King Tide approach.
    PERIOD_TIDE : str
        Period Tide approach.
    """
    KING_TIDE = "king_tide"
    PERIOD_TIDE = "period_tide"
