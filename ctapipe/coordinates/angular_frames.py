"""This module defines the important coordinate systems to be used in
reconstruction with the CTA pipeline and the transformations between
this different systems. Frames and transformations are defined using
the astropy.coordinates framework. This module contains transformations
between angular systems.

For examples on usage see examples/coordinate_transformations.py

This code is based on the coordinate transformations performed in the
read_hess code

TODO:

- Tests Tests Tests!
- Check cartesian system is still accurate for the nominal and
  telescope systems (may need a spherical system)
- Benchmark transformation time
- should use `astropy.coordinates.Angle` for all angles here
"""

import astropy.units as u
import numpy as np
from astropy.coordinates import (
    BaseCoordinateFrame,
    CartesianRepresentation,
    UnitSphericalRepresentation,
    FunctionTransform,
    CoordinateAttribute,
    QuantityAttribute,
    TimeAttribute,
    EarthLocationAttribute,
    AltAz
)


from astropy.coordinates import frame_transform_graph
from numpy import cos, sin, arctan, arctan2, arcsin, sqrt, arccos, tan
from ..coordinates.representation import PlanarRepresentation


__all__ = [
    'CameraFrame',
    'TelescopeFrame',
    'NominalFrame',
    'HorizonFrame'
]


class HorizonFrame(AltAz):
    """Horizon coordinate frame.

    Spherical system used to describe the direction
    of a given position, in terms of the altitude and azimuth of the system.
    This is functionally identical as the astropy AltAz system.
    """
    pass


class TelescopeFrame(BaseCoordinateFrame):
    """
    Telescope coordinate frame.

    Cartesian system describing the angular offset of a given position in reference
    to the pointing direction of a given telescope.

    This makes use of small angle approximations of the position of interest and
    the pointing direction.

    Frame attributes:

    * ``telescope_pointing``
        Coordinate of the telescope pointing in HorizonFrame
    * ``obstime``
        Observation time
    * ``location``
        Location of the telescope
    """
    default_representation = PlanarRepresentation

    telescope_pointing = CoordinateAttribute(default=None, frame=HorizonFrame)
    obstime = TimeAttribute(default=None)
    location = EarthLocationAttribute(default=None)


class NominalFrame(BaseCoordinateFrame):
    """Nominal coordinate frame. Cartesian system to describe the angular
    offset of a given telescope pointing with respect to a reference_point
    in the sky (in the HorizonFrame).
    In most cases this frame is the same as the telescope frame, however
    in the case of divergent pointing they will differ.
    Event reconstruction with HillasIntersection is performed in this system.

    Frame attributes:

    * ``reference_point``
        Alt,Az direction of the array pointing
    * ``obstime``
        Observation time
    * ``location``
        Location of the telescope
    """
    default_representation = PlanarRepresentation

    reference_point = CoordinateAttribute(frame=HorizonFrame, default=None)
    obstime = TimeAttribute(default=None)
    location = EarthLocationAttribute(default=None)


class CameraFrame(BaseCoordinateFrame):
    """Camera coordinate frame.  The camera frame is a simple physical
    cartesian frame, describing the 2 dimensional position of objects
    in the focal plane of the telescope Most Typically this will be
    used to describe the positions of the pixels in the focal plane

    Frame attributes:

    * ``focal_length``
        Focal length of the telescope as a unit quantity (usually meters)
    * ``rotation``
        Rotation angle of the camera (0 deg in most cases)
    """
    default_representation = PlanarRepresentation

    focal_length = QuantityAttribute(default=0, unit=u.m)
    rotation = QuantityAttribute(default=0 * u.deg, unit=u.rad)
    telescope_pointing = CoordinateAttribute(frame=HorizonFrame, default=None)

    obstime = TimeAttribute(default=None)
    location = EarthLocationAttribute(default=None)


# Transformations defined below this point

def altaz_to_offset(obj_azimuth, obj_altitude, azimuth, altitude):
    """
    Function to convert a given altitude and azimuth to a cartesian angular
    angular offset with regard to a give reference system
    (This function is directly lifted from read_hess)

    Parameters
    ----------
    obj_azimuth: float
        Event azimuth (radians)
    obj_altitude: float
        Event altitude (radians)
    azimuth: float
        Reference system azimuth (radians)
    altitude: float
        Reference system altitude (radians)

    Returns
    -------
    x_off,y_off: (float,float)
        Offset of the event in the reference system (in radians)
    """

    diff_az = obj_azimuth - azimuth
    cosine_obj_alt = cos(obj_altitude)

    xp0 = -cos(diff_az) * cosine_obj_alt
    yp0 = sin(diff_az) * cosine_obj_alt
    zp0 = sin(obj_altitude)

    sin_sys_alt = sin(altitude)
    cos_sys_alt = cos(altitude)

    xp1 = sin_sys_alt * xp0 + cos_sys_alt * zp0
    yp1 = yp0
    zp1 = -cos_sys_alt * xp0 + sin_sys_alt * zp0

    disp = tan(arccos(zp1))
    alpha = arctan2(yp1, xp1)

    x_off = disp * cos(alpha)
    y_off = disp * sin(alpha)

    return x_off, y_off


def offset_to_altaz(x_off, y_off, altitude, azimuth):
    """Function to convert an angular offset with regard to a give
    reference system to an an absolute altitude and azimuth (This
    function is directly lifted from read_hess)

    Parameters
    ----------
    x_off: float
        X offset of the event in the reference system
    y_off: float
        Y offset of the event in the reference system
    azimuth: float
        Reference system azimuth (radians)
    altitude: float
        Reference system altitude (radians)

    Returns
    -------
    obj_altitude,obj_azimuth: (float,float)
        Absolute altitude and azimuth of the event
    """

    unit = azimuth.unit

    x_off = x_off.to(u.rad).value
    y_off = y_off.to(u.rad).value
    azimuth = azimuth.to(u.rad).value
    altitude = altitude.to(u.rad).value

    offset = sqrt(x_off * x_off + y_off * y_off)
    pos = np.where(offset == 0)  # find offset 0 positions

    if len(pos[0]) > 0:
        if np.isscalar(offset):
            offset = 1e-14
        else:
            offset[pos] = 1e-14  # add a very small offset to prevent math errors

    atan_off = arctan(offset)

    sin_atan_off = sin(atan_off)
    xp1 = x_off * (sin_atan_off / offset)
    yp1 = y_off * (sin_atan_off / offset)
    zp1 = cos(atan_off)

    sin_obj_alt = sin(altitude)
    cos_obj_alt = cos(altitude)

    xp0 = sin_obj_alt * xp1 - cos_obj_alt * zp1
    yp0 = yp1
    zp0 = cos_obj_alt * xp1 + sin_obj_alt * zp1

    obj_altitude = arcsin(zp0)
    obj_azimuth = arctan2(yp0, -xp0) + azimuth

    if len(pos[0]) > 0:
        if np.isscalar(obj_altitude):
            obj_altitude = altitude
            obj_azimuth = azimuth
        else:
            obj_altitude[pos] = altitude
            obj_azimuth[pos] = azimuth

    obj_altitude = obj_altitude * u.rad
    obj_azimuth = obj_azimuth * u.rad

    # if obj_azimuth.value < 0.:
    #    obj_azimuth += 2.*pi
    # elif obj_azimuth.value >= (2.*pi ):
    #    obj_azimuth -= 2.*pi

    return obj_altitude.to(unit), obj_azimuth.to(unit)


@frame_transform_graph.transform(FunctionTransform, HorizonFrame, TelescopeFrame)
def horizon_to_telescope(horizon_coord, telescope_frame):
    """
    Transformation from HorizonFrame to TelescopeFrame

    Parameters
    ----------
    horizon_coord: `astropy.coordinates.SkyCoord`
        AltAz system
    telescope_frame: `ctapipe.coordinates.TelescopeFrame`
        nominal system

    Returns
    -------
    Coordinates in TelescopeFrame
    """
    alt_pointing = telescope_frame.telescope_pointing.alt
    az_pointing = telescope_frame.telescope_pointing.az

    x_off, y_off = altaz_to_offset(
        obj_azimuth=horizon_coord.az,
        obj_altitude=horizon_coord.alt,
        azimuth=az_pointing,
        altitude=alt_pointing,
    )
    x_off = x_off * u.rad
    y_off = y_off * u.rad

    representation = PlanarRepresentation(x_off, y_off)

    return telescope_frame.realize_frame(representation)


@frame_transform_graph.transform(FunctionTransform, TelescopeFrame, HorizonFrame)
def telescope_to_horizon(telescope_coord, horizon_frame):
    """
    Transformation from telescope system to astropy AltAz system

    Parameters
    ----------
    telescope_coord: `astropy.coordinates.SkyCoord`
        Coordinates in `TelescopeFrame`
    horizon_frame: `ctapipe.coordinates.HorizonFrame`
        frame to transform into

    Returns
    -------
    SkyCoord in horizon_frame
    """
    pointing = telescope_coord.telescope_pointing

    altitude, azimuth = offset_to_altaz(
        telescope_coord.x,
        telescope_coord.y,
        altitude=pointing.alt,
        azimuth=pointing.az,
    )

    representation = UnitSphericalRepresentation(lon=azimuth, lat=altitude)
    return horizon_frame.realize_frame(representation)


# Transformation between nominal and AltAz system


@frame_transform_graph.transform(FunctionTransform, NominalFrame, HorizonFrame)
def nominal_to_altaz(norm_coord, altaz_coord):
    """
    Transformation from nominal system to astropy AltAz system

    Parameters
    ----------
    norm_coord: `astropy.coordinates.SkyCoord`
        nominal system
    altaz_coord: `astropy.coordinates.SkyCoord`
        AltAz system

    Returns
    -------
    AltAz Coordinates
    """
    alt_nom, az_nom = norm_coord.reference_point.alt, norm_coord.reference_point.az

    x_off = norm_coord.x
    y_off = norm_coord.y

    altitude, azimuth = offset_to_altaz(
        x_off,
        y_off,
        azimuth=az_nom,
        altitude=alt_nom,
    )

    representation = UnitSphericalRepresentation(lon=azimuth, lat=altitude)
    return altaz_coord.realize_frame(representation)


@frame_transform_graph.transform(FunctionTransform, HorizonFrame, NominalFrame)
def altaz_to_nominal(altaz_coord, norm_coord):
    """
    Transformation from astropy AltAz system to nominal system

    Parameters
    ----------
    altaz_coord: `astropy.coordinates.SkyCoord`
        AltAz system
    norm_coord: `astropy.coordinates.SkyCoord`
        nominal system

    Returns
    -------
    nominal Coordinates
    """
    alt_nom, az_nom = norm_coord.reference_point.alt, norm_coord.reference_point.az
    azimuth = altaz_coord.az
    altitude = altaz_coord.alt
    x_off, y_off = altaz_to_offset(azimuth, altitude, az_nom, alt_nom)
    x_off = x_off * u.rad
    y_off = y_off * u.rad
    representation = PlanarRepresentation(x_off, y_off)

    return norm_coord.realize_frame(representation)


# Transformation between telescope and nominal frames


@frame_transform_graph.transform(FunctionTransform, TelescopeFrame, NominalFrame)
def telescope_to_nominal(tel_coord, nominal_frame):
    """
    Coordinate transformation from telescope frame to nominal frame

    Parameters
    ----------
    tel_coord: `astropy.coordinates.SkyCoord`
        TelescopeFrame system
    nominal_frame: `astropy.coordinates.SkyCoord`
        NominalFrame system

    Returns
    -------
    NominalFrame coordinates
    """
    alt_tel, az_tel = tel_coord.telescope_pointing.alt, tel_coord.telescope_pointing.az
    alt_nom, az_nom = nominal_frame.reference_point.alt, nominal_frame.reference_point.az

    alt_trans, az_trans = offset_to_altaz(
        tel_coord.x, tel_coord.y,
        altitude=alt_tel,
        azimuth=az_tel,
    )

    x_off, y_off = altaz_to_offset(az_trans, alt_trans, az_nom, alt_nom)
    x_off = x_off * u.rad
    y_off = y_off * u.rad

    representation = PlanarRepresentation(x_off, y_off)

    return nominal_frame.realize_frame(representation)


@frame_transform_graph.transform(FunctionTransform, NominalFrame, TelescopeFrame)
def nominal_to_telescope(norm_coord, tel_frame):
    """
    Coordinate transformation from nominal to telescope system

    Parameters
    ----------
    norm_coord: `astropy.coordinates.SkyCoord`
        NominalFrame system
    tel_frame: `astropy.coordinates.SkyCoord`
        TelescopeFrame system

    Returns
    -------
    TelescopeFrame coordinates

    """
    alt_tel, az_tel = tel_frame.telescope_pointing.alt, tel_frame.telescope_pointing.az
    alt_nom, az_nom = norm_coord.reference_point.alt, norm_coord.reference_point.az

    alt_trans, az_trans = offset_to_altaz(
        norm_coord.x,
        norm_coord.y,
        azimuth=az_nom,
        altitude=alt_nom,
    )

    x_off, y_off = altaz_to_offset(az_trans, alt_trans, az_tel, alt_tel)
    x_off = x_off * u.rad
    y_off = y_off * u.rad

    representation = PlanarRepresentation(
        x_off.to(norm_coord.x.unit),
        y_off.to(norm_coord.x.unit),
    )

    return tel_frame.realize_frame(representation)


# Transformations between camera frame and telescope frame
@frame_transform_graph.transform(FunctionTransform, CameraFrame, TelescopeFrame)
def camera_to_telescope(camera_coord, telescope_frame):
    """
    Transformation between CameraFrame and TelescopeFrame

    Parameters
    ----------
    camera_coord: `astropy.coordinates.SkyCoord`
        CameraFrame system
    telescope_frame: `astropy.coordinates.SkyCoord`
        TelescopeFrame system
    Returns
    -------
    TelescopeFrame coordinate
    """
    x_pos = camera_coord.cartesian.x
    y_pos = camera_coord.cartesian.y

    rot = camera_coord.rotation
    if rot == 0:
        x_rotated = x_pos
        y_rotated = y_pos
    else:
        x_rotated = x_pos * cos(rot) - y_pos * sin(rot)
        y_rotated = x_pos * sin(rot) + y_pos * cos(rot)

    focal_length = camera_coord.focal_length

    x_rotated = (x_rotated / focal_length).to_value() * u.rad
    y_rotated = (y_rotated / focal_length).to_value() * u.rad
    representation = PlanarRepresentation(x_rotated, y_rotated)

    return telescope_frame.realize_frame(representation)


@frame_transform_graph.transform(FunctionTransform, TelescopeFrame, CameraFrame)
def telescope_to_camera(telescope_coord, camera_frame):
    """
    Transformation between TelescopeFrame and CameraFrame

    Parameters
    ----------
    telescope_coord: `astropy.coordinates.SkyCoord`
        TelescopeFrame system
    camera_frame: `astropy.coordinates.SkyCoord`
        CameraFrame system

    Returns
    -------
    CameraFrame Coordinates
    """
    x_pos = telescope_coord.x
    y_pos = telescope_coord.y
    # reverse the rotation applied to get to this system
    rot = -camera_frame.rotation

    if rot.value == 0.0:  # if no rotation applied save a few cycles
        x_rotated = x_pos
        y_rotated = y_pos
    else:  # or else rotate all positions around the camera centre
        cosrot = np.cos(rot)
        sinrot = np.sin(rot)
        x_rotated = x_pos * cosrot - y_pos * sinrot
        y_rotated = x_pos * sinrot + y_pos * cosrot

    focal_length = camera_frame.focal_length
    # Remove distance units here as we are using small angle approx
    x_rotated = x_rotated.to_value(u.rad) * focal_length
    y_rotated = y_rotated.to_value(u.rad) * focal_length

    representation = CartesianRepresentation(
        x_rotated,
        y_rotated,
        0 * u.m
    )

    return camera_frame.realize_frame(representation)
