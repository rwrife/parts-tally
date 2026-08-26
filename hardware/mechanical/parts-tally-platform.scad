// Parts Tally parametric scale platform, revision A0.
// Editable source; all dimensions are millimetres.
//
// Manufacturer basis: HT Sensor TAL220B drawing (SparkFun-hosted PDF,
// SHA-256 641b4150...21181) gives 55 x 12.7 x 12.7 mm body, 40 mm
// mounting-hole spacing, and M5 passages.  Measure the purchased cell before
// fabrication.  This model is unbuilt and carries no physical-test claim.

$fn = 48;
part = "assembly"; // assembly | base | platform | cell | board | stop_gauge
join_overlap = 0.1; // ensure touching features compile as one printable solid

base_size = [170, 120, 6];
base_corner_r = 6;
platform_size = [130, 90, 4];
platform_corner_r = 5;
platform_z = 34;

load_cell_size = [55, 12.7, 12.7];
load_cell_hole_spacing = 40;
load_cell_hole_d = 5.2;
load_cell_z = 15;
fixed_hole_x = -load_cell_hole_spacing / 2;
free_hole_x = load_cell_hole_spacing / 2;
free_bracket_height = platform_z-load_cell_z-load_cell_size[2];
cell_mount_size = [18, 24];
fixed_mount_origin = [fixed_hole_x-cell_mount_size[0]/2,
                      -cell_mount_size[1]/2];
free_mount_origin = [free_hole_x-cell_mount_size[0]/2,
                     -cell_mount_size[1]/2];
assert_epsilon = 0.000001;

// Keep both printed M5 passages exactly collinear with the load-cell drawing.
// These assertions run during every OpenSCAD export and fail closed if a
// future origin/size edit moves either mount away from its cell hole.
assert(abs(fixed_mount_origin[0]+cell_mount_size[0]/2-fixed_hole_x) < assert_epsilon);
assert(abs(fixed_mount_origin[1]+cell_mount_size[1]/2) < assert_epsilon);
assert(abs(free_mount_origin[0]+cell_mount_size[0]/2-free_hole_x) < assert_epsilon);
assert(abs(free_mount_origin[1]+cell_mount_size[1]/2) < assert_epsilon);

pcb_size = [100, 60, 1.6];
pcb_z = 10;
// Coordinates are the actual KiCad hole locations translated by board centre.
pcb_holes = [[-46,-26], [14,-26], [-46,26], [46,26]];
pcb_standoff_od = 7;
pcb_hole_d = 3.2;

foot_holes = [[-75,-50], [75,-50], [-75,50], [75,50]];
foot_hole_d = 4.2;
stop_positions = [[-48,-34], [-48,34], [48,-34], [48,34]];
stop_boss_od = 10;
stop_contact_pad_od = 12;
stop_contact_pad_thickness = 2;
stop_nominal_gap = 0.8; // set physically below 120% FS; do not trust print tolerance
stop_contact_plane_z = platform_z-stop_contact_pad_thickness;
stop_boss_height = 18;
stop_boss_top = base_size[2]+stop_boss_height;
stop_insert_od = 6.2; // verify against the selected M4 heat-set insert
stop_insert_depth = 6;
stop_set_screw_d = 4;
stop_set_screw_contact_z = stop_contact_plane_z-stop_nominal_gap;
stop_set_screw_length = stop_set_screw_contact_z-(stop_boss_top-stop_insert_depth);
assert(abs(stop_contact_plane_z-stop_set_screw_contact_z-stop_nominal_gap) < assert_epsilon);
assert(stop_set_screw_length > 12 && stop_set_screw_length < 16);
assert(stop_contact_pad_od > stop_set_screw_d);

module rounded_plate(size, radius, height) {
    linear_extrude(height)
        hull()
            for (x=[-size[0]/2+radius, size[0]/2-radius],
                 y=[-size[1]/2+radius, size[1]/2-radius])
                translate([x,y]) circle(r=radius);
}

module base() {
    difference() {
        union() {
            rounded_plate([base_size[0], base_size[1]], base_corner_r, base_size[2]);
            // PCB standoffs are separate from the load-cell force path.
            for (p=pcb_holes)
                translate([p[0], p[1], base_size[2]-join_overlap])
                    difference() {
                        cylinder(h=pcb_z-base_size[2]+join_overlap, d=pcb_standoff_od);
                        cylinder(h=pcb_z-base_size[2]+0.2, d=pcb_hole_d);
                    }
            // Fixed-end cell support: only this boss loads the base.
            translate([fixed_mount_origin[0], fixed_mount_origin[1],
                       base_size[2]-join_overlap])
                cube([cell_mount_size[0], cell_mount_size[1],
                      load_cell_z-base_size[2]+join_overlap], center=false);
            // Adjustable overload-stop bosses bypass both cell and PCB at limit.
            for (p=stop_positions)
                translate([p[0],p[1],base_size[2]-join_overlap])
                    difference() {
                        cylinder(h=stop_boss_height+join_overlap, d=stop_boss_od);
                        translate([0,0,stop_boss_height-stop_insert_depth])
                            cylinder(h=stop_insert_depth+join_overlap,
                                     d=stop_insert_od);
                    }
            // Two-piece cable clamp land; cable exits toward the left side.
            translate([-48,-11,base_size[2]-join_overlap])
                cube([20,22,3+join_overlap]);
        }
        for (p=foot_holes)
            translate([p[0],p[1],-0.1]) cylinder(h=base_size[2]+0.2, d=foot_hole_d);
        // Fixed M5 cell passage.
        translate([fixed_hole_x,0,-0.1])
            cylinder(h=load_cell_z+1, d=load_cell_hole_d);
        // Strain-relief cable channel and M3 clamp holes.
        translate([-55,-3,-0.1]) cube([24,6,base_size[2]+4]);
        for (y=[-7,7]) translate([-42,y,-0.1]) cylinder(h=base_size[2]+5,d=3.2);
    }
}

module platform() {
    difference() {
        union() {
            rounded_plate([platform_size[0], platform_size[1]], platform_corner_r,
                          platform_size[2]);
            // Bin cradle rails keep a removable bin centred without claiming a fit.
            for (y=[-platform_size[1]/2+5, platform_size[1]/2-5])
                translate([-platform_size[0]/2+8,y-2,platform_size[2]-join_overlap])
                    cube([platform_size[0]-16,4,8+join_overlap]);
            // Free-end bracket connects only to the load cell.
            translate([free_mount_origin[0],free_mount_origin[1],
                       -free_bracket_height])
                difference() {
                    cube([cell_mount_size[0],cell_mount_size[1],
                          free_bracket_height+join_overlap]);
                    translate([cell_mount_size[0]/2,cell_mount_size[1]/2,-0.1])
                        cylinder(h=platform_z, d=load_cell_hole_d);
                }
            // Solid underside pads provide a real collision surface for the
            // adjustable M4 stop heads; adjustment is made before installing
            // the top platform, so no access hole defeats the stop.
            for (p=stop_positions)
                translate([p[0],p[1],-stop_contact_pad_thickness])
                    cylinder(h=stop_contact_pad_thickness+join_overlap,
                             d=stop_contact_pad_od);
        }
    }
}

module load_cell_reference() {
    color([0.7,0.7,0.72])
    difference() {
        translate([-load_cell_size[0]/2,-load_cell_size[1]/2,0]) cube(load_cell_size);
        for (x=[fixed_hole_x,free_hole_x])
            translate([x,0,-0.1]) cylinder(h=load_cell_size[2]+0.2,d=load_cell_hole_d);
    }
}

module pcb_reference() {
    color([0.05,0.35,0.15,0.75])
    difference() {
        translate([-pcb_size[0]/2,-pcb_size[1]/2,0]) cube(pcb_size);
        for (p=pcb_holes)
            translate([p[0],p[1],-0.1]) cylinder(h=pcb_size[2]+0.2,d=pcb_hole_d);
    }
    // XIAO antenna mechanical keepout, transformed from the KiCad rule area.
    // No fastener, cable loop, shield, or metal enclosure feature may enter.
    color([1,0.3,0.1,0.28])
        translate([23,-19,pcb_size[2]]) cube([12,28,12]);
}

module feet_reference() {
    color([0.1,0.1,0.1])
    for (p=foot_holes)
        translate([p[0],p[1],-3]) cylinder(h=3,d=16);
}

module stop_hardware_reference() {
    // Reference only: M4 nylon-tip set screws in heat-set inserts, locked with
    // jam nuts. The screw-tip plane—not the boss top—defines the nominal gap.
    for (p=stop_positions) {
        color([0.75,0.55,0.18])
            translate([p[0],p[1],stop_boss_top-stop_insert_depth])
                cylinder(h=stop_insert_depth,d=stop_insert_od);
        color([0.55,0.57,0.6])
            translate([p[0],p[1],stop_boss_top-stop_insert_depth])
                cylinder(h=stop_set_screw_length,d=stop_set_screw_d);
        color([0.45,0.45,0.47])
            translate([p[0],p[1],stop_boss_top])
                cylinder(h=3,d=7,$fn=6);
    }
}

module stop_gap_gauge() {
    // Print only as a setup aid; verify the real stop under controlled loading.
    cube([30,12,stop_nominal_gap]);
}

module assembly() {
    color([0.18,0.2,0.22]) base();
    feet_reference();
    translate([0,0,load_cell_z]) load_cell_reference();
    translate([0,0,pcb_z]) pcb_reference();
    stop_hardware_reference();
    color([0.82,0.84,0.86,0.75]) translate([0,0,platform_z]) platform();
}

if (part == "base") base();
else if (part == "platform") platform();
else if (part == "cell") load_cell_reference();
else if (part == "board") pcb_reference();
else if (part == "stop_gauge") stop_gap_gauge();
else assembly();
