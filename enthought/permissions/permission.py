#------------------------------------------------------------------------------
# Copyright (c) 2008, Riverbank Computing Limited
# All rights reserved.
#
# This software is provided without warranty under the terms of the BSD
# license included in enthought/LICENSE.txt and may be redistributed only
# under the conditions described in the aforementioned license.  The license
# is also available online at http://www.enthought.com/licenses/BSD.txt
# Thanks for using Enthought open source!
#
# Author: Riverbank Computing Limited
# Description: <Enthought permissions package component>
#------------------------------------------------------------------------------


# Enthought library imports.
from enthought.traits.api import Bool, HasTraits, Property, Str, Unicode

# Locals imports.
from permissions_manager import PermissionsManager


class Permission(HasTraits):
    """A permission is the link between an application action and the current
    user - if the user has a permission attached to the action then the user is
    allowed to perform that action."""

    #### 'Permission' interface ###############################################

    # The id of the permission.  By convention a dotted format is used for the
    # id with the id of the application being the first part.
    id = Str

    # A user friendly description of the permission.
    description = Unicode

    # Set if the current user has this permission.  This is typically used with
    # the enabled_when and visible_when traits of a TraitsUI Item object when
    # the permission instance has been placed in the TraitsUI context.
    granted = Property

    # Set if the permission should be granted automatically when bootstrapping.
    # This is normally only ever set for permissions related to user management
    # and permissions.  The user manager determines exactly what is meant by
    # "bootstrapping" but it is usually when it determines that no user or
    # permissions information has been defined.
    bootstrap = Bool(False)

    # Set if the permission has been defined by application code rather than as
    # a result of loading the policy database.
    application_defined = Bool(True)

    ###########################################################################
    # 'object' interface.
    ###########################################################################

    def __init__(self, **traits):
        """Initialise the object."""

        super(Permission, self).__init__(**traits)

        # Register the permission.
        PermissionsManager.policy_manager.register_permission(self)

    def __str__(self):
        """Return a user friendly representation."""

        s = self.description
        if not s:
            s = self.id

        return s

    ###########################################################################
    # Trait handlers.
    ###########################################################################

    def _get_granted(self):
        """Check the user has this permission."""

        return PermissionsManager.check_permissions(self)


def ManagePolicyPermission():
    """Return the standard permission for managing permissions policies."""

    return Permission(id='ets.permissions.manage_policy',
            description=u"Manage policy", bootstrap=True)


def ManageUsersPermission():
    """Return the standard permission for managing permissions users."""

    return Permission(id='ets.permissions.manage_users',
            description=u"Manage users", bootstrap=True)
