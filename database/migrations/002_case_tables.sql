-- =============================================================================
-- Migration 002: Case tables (CaseMaster and its children)
-- Source: docs/architecture/Police_FIR_ER_Diagram.pdf. Depends on every
-- table created in 001_lookup_and_org_tables.sql.
--
-- Notable inferences/corrections from the source PDF (everything else is
-- taken directly from the document):
--   - Inv_OccuranceTime: the PDF lists IncidentFromDate/IncidentToDate/
--     InfoReceivedPSDate/latitude/longitude/BriefFacts directly under
--     CaseMaster's field list with no new table header, but the Relationship
--     Matrix explicitly names "Inv_OccuranceTime" as a separate one-to-one
--     child table of CaseMaster - modeled as such here.
--   - ActSectionAssociation.ActID / SectionID: source types them INT, but
--     Act.ActCode / Section.SectionCode (the columns they reference) are
--     VARCHAR primary keys - typed VARCHAR here to actually be valid FKs.
--   - inv_arrestsurrenderaccused: only named in the Relationship Matrix
--     ("links ArrestSurrender to multiple Accused"), no column list given in
--     the table definitions section. Columns inferred as the obvious
--     junction of (ArrestSurrenderID, AccusedMasterID).
--   - ChargesheetDetails.PolicePersonID: source says
--     "FK -> employeeMaster.employee ID" (lowercase, doesn't match any
--     table name used elsewhere in the doc) - treated as Employee.EmployeeID,
--     consistent with every other PolicePersonID/IOID FK in the document.
-- =============================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE CaseMaster (
    CaseMasterID        INTEGER PRIMARY KEY AUTOINCREMENT,
    CrimeNo              VARCHAR(20) NOT NULL UNIQUE,
    -- Format: 1-digit CaseCategory code + 4-digit District ID + 4-digit
    -- Unit(PS) ID + 4-digit year + 5-digit running serial, e.g. 104430006202600001
    CaseNo               VARCHAR(15) NOT NULL,
    -- YYYY + 5-digit running serial (last 9 digits of CrimeNo)
    CrimeRegisteredDate  DATE NOT NULL,
    PolicePersonID       INTEGER REFERENCES Employee(EmployeeID),
    PoliceStationID      INTEGER REFERENCES Unit(UnitID),
    CaseCategoryID       INTEGER REFERENCES CaseCategory(CaseCategoryID),
    GravityOffenceID     INTEGER REFERENCES GravityOffence(GravityOffenceID),
    CrimeMajorHeadID     INTEGER REFERENCES CrimeHead(CrimeHeadID),
    CrimeMinorHeadID     INTEGER REFERENCES CrimeSubHead(CrimeSubHeadID),
    CaseStatusID         INTEGER REFERENCES CaseStatusMaster(CaseStatusID),
    CourtID              INTEGER REFERENCES Court(CourtID)
);

CREATE TABLE Inv_OccuranceTime (
    CaseMasterID        INTEGER PRIMARY KEY REFERENCES CaseMaster(CaseMasterID),
    IncidentFromDate     DATETIME,
    IncidentToDate       DATETIME,
    InfoReceivedPSDate   DATETIME,
    latitude             DECIMAL(9,6),
    longitude            DECIMAL(9,6),
    BriefFacts           TEXT
);

CREATE TABLE ComplainantDetails (
    ComplainantID   INTEGER PRIMARY KEY AUTOINCREMENT,
    CaseMasterID    INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    ComplainantName VARCHAR(150) NOT NULL,
    AgeYear         INTEGER,
    OccupationID    INTEGER REFERENCES OccupationMaster(OccupationID),
    ReligionID      INTEGER REFERENCES ReligionMaster(ReligionID),
    CasteID         INTEGER REFERENCES CasteMaster(caste_master_id),
    GenderID        INTEGER REFERENCES GenderMaster(GenderID)
);

CREATE TABLE ActSectionAssociation (
    CaseMasterID   INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    ActID          VARCHAR(20) NOT NULL REFERENCES Act(ActCode),
    SectionID      VARCHAR(20) NOT NULL REFERENCES Section(SectionCode),
    ActOrderID     INTEGER,
    SectionOrderID INTEGER,
    PRIMARY KEY (CaseMasterID, ActID, SectionID)
);

CREATE TABLE Victim (
    VictimMasterID INTEGER PRIMARY KEY AUTOINCREMENT,
    CaseMasterID   INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    VictimName     VARCHAR(150) NOT NULL,
    AgeYear        INTEGER,
    GenderID       INTEGER REFERENCES GenderMaster(GenderID),
    VictimPolice   VARCHAR(1) DEFAULT '0' CHECK (VictimPolice IN ('0', '1'))
);

CREATE TABLE Accused (
    AccusedMasterID INTEGER PRIMARY KEY AUTOINCREMENT,
    CaseMasterID    INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    AccusedName     VARCHAR(150) NOT NULL,
    AgeYear         INTEGER,
    GenderID        INTEGER REFERENCES GenderMaster(GenderID),
    PersonID        VARCHAR(10)   -- display sort label within the case: A1, A2, A3...
);

CREATE TABLE ArrestSurrender (
    ArrestSurrenderID       INTEGER PRIMARY KEY AUTOINCREMENT,
    CaseMasterID            INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    ArrestSurrenderTypeID   INTEGER REFERENCES ArrestSurrenderTypeMaster(ArrestSurrenderTypeID),
    ArrestSurrenderDate     DATE,
    ArrestSurrenderStateId  INTEGER REFERENCES State(StateID),
    ArrestSurrenderDistrictId INTEGER REFERENCES District(DistrictID),
    PoliceStationID         INTEGER REFERENCES Unit(UnitID),
    IOID                    INTEGER REFERENCES Employee(EmployeeID),
    CourtID                 INTEGER REFERENCES Court(CourtID),
    AccusedMasterID         INTEGER REFERENCES Accused(AccusedMasterID),
    IsAccused               INTEGER CHECK (IsAccused IN (0, 1)),
    IsComplainantAccused    INTEGER CHECK (IsComplainantAccused IN (0, 1))
);

-- Columns inferred from the Relationship Matrix - see migration header note.
CREATE TABLE inv_arrestsurrenderaccused (
    ArrestSurrenderID INTEGER NOT NULL REFERENCES ArrestSurrender(ArrestSurrenderID),
    AccusedMasterID   INTEGER NOT NULL REFERENCES Accused(AccusedMasterID),
    PRIMARY KEY (ArrestSurrenderID, AccusedMasterID)
);

CREATE TABLE ChargesheetDetails (
    CSID           INTEGER PRIMARY KEY AUTOINCREMENT,
    CaseMasterID   INTEGER NOT NULL REFERENCES CaseMaster(CaseMasterID),
    csdate         DATETIME,
    cstype         CHAR(1) CHECK (cstype IN ('A', 'B', 'C')),  -- A=Chargesheet, B=False Case, C=Undetected
    PolicePersonID INTEGER REFERENCES Employee(EmployeeID)
);

CREATE INDEX idx_casemaster_district_unit ON CaseMaster(PoliceStationID);
CREATE INDEX idx_casemaster_status ON CaseMaster(CaseStatusID);
CREATE INDEX idx_casemaster_registered_date ON CaseMaster(CrimeRegisteredDate);
CREATE INDEX idx_victim_case ON Victim(CaseMasterID);
CREATE INDEX idx_accused_case ON Accused(CaseMasterID);
CREATE INDEX idx_complainant_case ON ComplainantDetails(CaseMasterID);
CREATE INDEX idx_arrestsurrender_accused ON ArrestSurrender(AccusedMasterID);
