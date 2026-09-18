// The requirements this job must meet. They belong to the machine, not to the
// brand that happens to fill the job today.
package LinearGuideX {

    requirement def XGuideStiffness {
        doc /* Deflection under a 200 N side load stays below 0.02 mm. */
    }

    requirement def XGuideTravel {
        doc /* Usable carriage travel of at least 320 mm. */
    }

    // What the role needs from whatever fills it. A library part that fits
    // declares the matching provides-interface in its own manifest.
    port def LinearGuide20MountInterface;
}
