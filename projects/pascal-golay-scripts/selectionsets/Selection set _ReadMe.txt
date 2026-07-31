Use this plug-in for saving and retrieving and managing selections of objects or grips (control points) that you care enough about to want to keep or be able to reselect. Selection sets are saved in the Rhino file. **A major limitation is that these commands do not work for selecting points inside other commands, at least so far. Only preselection works.**


Grip selection Commands- these work on any sort of grips that can be turned on using the PointsOn command,- curve and surface control points, cage control points, mesh points, blocks (insertion points) but not on curve edit points. 

GripSelectionSet-
If you have grips or control points selected you will be asked to name the selection set for these. Any previously defined sets will show up as clickable options at the command line- if you choose one of these as the name, the set will be redefined. This allows you to add or subtract points from an existing set by first selecting the set(commands below), then adding or subtracting points, then use this command to redefine the set. It also helps you keep the number of sets down - you can choose the name of a set that is no longer needed and redefine it.

If no objects have points on, you should get a polite message...


SelGripsList-
This presents a list of the named sets- you can select one or more from the list and all the points will be selected. If control points are not on on these objects, they will be turned on.


SelGripsName-
As above, but instead of a list, you can type the name of the set. This is mainly for making macros like this:

  SelGripsName "SetName"

Multiple names work as well:

  SelGripsName Name1,"name 2",NameX
  (Comma separated names, no spaces between comma and name)



DeleteGripSets-
Select one or more sets from a list to delete the sets. This is so you can pare down the list if you find a project starts to make more sets than is useful.



RenameGripSet-
Rename a set.


SubtractGripSets -
Subtract one or more sets from the current selection.


Object selection commands- these correspond pretty closely to the grip ones:

SelectionSet

SelSetList

SelSetName (mostly for scripting or making buttons, typing in multiple names separated by a comma does work)

DeleteSeletionSets

RenameSelectionSet

SubtractSetsList

SubtractSetsName

Point Bucket Toolbar:
Four 'point buckets', A-D.

Save the current point selection to the bucket.
This replaces any current set in that bucket. LMB


Plus sign-
Add the bucket to the current selection. LMB
Deselect all and then select just the bucket(s). RMB

Minus sign-
Subtract the bucket from the current selection. LMB