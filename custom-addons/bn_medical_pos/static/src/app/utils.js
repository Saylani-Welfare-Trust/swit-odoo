/** @odoo-module */

/** Lower-cased tag names of a partner as loaded in the POS (`categories` is "Donee, Individual, Medical") */
export function partnerTagNames(partner) {
    return (partner?.categories || "")
        .split(",")
        .map((name) => name.trim().toLowerCase())
        .filter(Boolean);
}

/** Patients are donees tagged Medical (not "Medical Equipment") */
export function isMedicalPatient(partner) {
    const tags = partnerTagNames(partner);
    return tags.includes("donee") && tags.includes("medical");
}
