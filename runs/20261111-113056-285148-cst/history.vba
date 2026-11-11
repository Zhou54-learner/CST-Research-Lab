With Units
 .Geometry "mm"
 .Frequency "GHz"
 .Time "ns"
End With
With Background
 .Type "Normal"
 .Epsilon "1"
 .Mue "1"
 .XminSpace "0"
 .XmaxSpace "0"
 .YminSpace "0"
 .YmaxSpace "0"
 .ZminSpace "0"
 .ZmaxSpace "0"
End With
With Brick
 .Reset
 .Name "vacuum_guide"
 .Component "smoke"
 .Material "Vacuum"
 .Xrange "0", "22.86"
 .Yrange "0", "10.16"
 .Zrange "0", "12.0"
 .Create
End With
With Boundary
 .Xmin "electric"
 .Xmax "electric"
 .Ymin "electric"
 .Ymax "electric"
 .Zmin "electric"
 .Zmax "electric"
End With
Solver.FrequencyRange "8", "12"
With Port
 .Reset
 .PortNumber "1"
 .NumberOfModes "1"
 .Coordinates "Full"
 .Orientation "zmin"
 .PortOnBound "True"
 .Create
End With
With Port
 .Reset
 .PortNumber "2"
 .NumberOfModes "1"
 .Coordinates "Full"
 .Orientation "zmax"
 .PortOnBound "True"
 .Create
End With
ChangeSolverType "HF Time Domain"
With Solver
 .Method "Hexahedral"
 .CalculationType "TD-S"
 .StimulationPort "1"
 .StimulationMode "1"
 .SteadyStateLimit "-40"
End With
