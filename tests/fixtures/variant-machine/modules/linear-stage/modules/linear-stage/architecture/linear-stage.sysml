package LinearStage {
    requirement def TravelRequirement {
        doc /* Each model of the stage shall give the travel it promises.
               The guide rail length sets that travel. */
        attribute rail_length_mm : Real;
    }
}
