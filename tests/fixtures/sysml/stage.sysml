// A small stage, written like a real module file: comments that hold
// braces { and semicolons ; and the words part def, which the scanner
// must ignore.
package Stage {
    private import ScalarValues::*;
    private import ISQ::*;
    private import SI::*;

    // Interfaces to the outside. okh.toml lists them too.
    port def BaseMountInterface_v1 {
        doc /*
         * The bottom face of the base, where the stage screws onto the
         * machine.
         */
        attribute holePitch : LengthValue;
    }

    port def RailMountInterface_v1 {
        doc /* A guide rail lies on the floor of the base; see "notes {x}". */
        attribute holePitch : LengthValue = 60 [mm];
        attribute holesPerRail : Natural = 7;   // one row
    }

    port def ClampMountInterface_v1;

    part def Base {
        doc /* The fixed body of the stage. CAD: cad/parts/base/. */
        port machineMount : BaseMountInterface_v1;
        port referenceRailMount : RailMountInterface_v1;
    }

    part def GuideRail {
        doc /* A bought rail from the parts library. */
        port baseMount : ~RailMountInterface_v1;
    }

    part def Stage {
        doc /* The whole stage. */
        attribute travel : LengthValue;      // usable stroke
        attribute width : LengthValue;

        part base : Base;
        part referenceRail : GuideRail;

        port machineMount : BaseMountInterface_v1;
        bind machineMount = base.machineMount;

        // The guide rails
        connect base.referenceRailMount to referenceRail.baseMount;
    }

    package Mandatory {

        requirement def <'STG-01'> Width {
            doc /* The stage is at most 210 mm wide. */
            subject stage : Stage;
            require constraint { stage.width <= 210 [mm] }
        }

        requirement def <'STG-03'> Length {
            doc /*
             * The stage is at most (travel + 340 mm - 2 x height) long.
             */
            subject stage : Stage;
            require constraint {
                stage.length <= stage.travel + 340 [mm] - 2 * stage.height
            }
        }
    }

    requirement def StageSpecification {
        doc /* All requirements for one stage. */
        subject stage : Stage;

        requirement width : Mandatory::Width;
        requirement length : Mandatory::Length;
    }
}
