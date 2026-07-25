-- =============================================================================
-- Migration 001: Lookup / master / organizational tables
-- Source: docs/architecture/Police_FIR_ER_Diagram.pdf (Karnataka Police
-- Department FIR System ER Diagram - CONFIDENTIAL, internal reference only).
-- This migration creates every table that CaseMaster and its children (see
-- 002_case_tables.sql) depend on, in FK dependency order.
--
-- Target: SQLite for local/demo use (file-based, zero-config). Types are
-- kept standard (INTEGER/VARCHAR/DATE/DECIMAL) so this ports cleanly to
-- Postgres/SQL Server for a real deployment - see docs/architecture/Zoho
-- Catalyst Deployment... for the production data-store target.
--
-- Two lookup tables (GenderMaster, ArrestSurrenderTypeMaster) are additions
-- NOT explicitly detailed as their own tables in the source PDF - the source
-- only says "(lookup value)" next to GenderID/ArrestSurrenderTypeID columns
-- without defining the table. Added here for referential integrity; every
-- other table/column follows the source document exactly. Section's primary
-- key is likewise an inference (the source PDF doesn't mark a key for
-- Section at all) - SectionCode is made the PK since
-- ActSectionAssociation.SectionID references it as a single column.
-- =============================================================================

PRAGMA foreign_keys = ON;

CREATE TABLE State (
    StateID      INTEGER PRIMARY KEY AUTOINCREMENT,
    StateName    VARCHAR(100) NOT NULL,
    NationalityID INTEGER,
    Active       INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE District (
    DistrictID   INTEGER PRIMARY KEY AUTOINCREMENT,
    DistrictName VARCHAR(100) NOT NULL,
    StateID      INTEGER NOT NULL REFERENCES State(StateID),
    Active       INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE UnitType (
    UnitTypeID   INTEGER PRIMARY KEY AUTOINCREMENT,
    UnitTypeName VARCHAR(100) NOT NULL,       -- e.g. Police Station, Circle Office
    CityDistState VARCHAR(20),                -- operational level: City / District / State
    Hierarchy    INTEGER,                     -- lower = higher authority
    Active       INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE Unit (
    UnitID       INTEGER PRIMARY KEY AUTOINCREMENT,
    UnitName     VARCHAR(150) NOT NULL,
    TypeID       INTEGER REFERENCES UnitType(UnitTypeID),
    ParentUnit   INTEGER REFERENCES Unit(UnitID),   -- self-reference for hierarchy
    NationalityID INTEGER,
    StateID      INTEGER REFERENCES State(StateID),
    DistrictID   INTEGER REFERENCES District(DistrictID),
    Active       INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE Rank (
    RankID       INTEGER PRIMARY KEY AUTOINCREMENT,
    RankName     VARCHAR(100) NOT NULL,   -- e.g. Constable, Inspector, DSP
    Hierarchy    INTEGER,                 -- lower = higher rank
    Active       INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE Designation (
    DesignationID   INTEGER PRIMARY KEY AUTOINCREMENT,
    DesignationName VARCHAR(100) NOT NULL,  -- e.g. Investigating Officer, SHO
    Active          INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1)),
    SortOrder       INTEGER
);

CREATE TABLE GenderMaster (
    GenderID    INTEGER PRIMARY KEY AUTOINCREMENT,
    GenderCode  VARCHAR(1) NOT NULL UNIQUE,   -- M / F / T
    GenderName  VARCHAR(20) NOT NULL
);

CREATE TABLE Employee (
    EmployeeID       INTEGER PRIMARY KEY AUTOINCREMENT,
    DistrictID       INTEGER REFERENCES District(DistrictID),
    UnitID           INTEGER REFERENCES Unit(UnitID),
    RankID           INTEGER REFERENCES Rank(RankID),
    DesignationID    INTEGER REFERENCES Designation(DesignationID),
    KGID             VARCHAR(30) UNIQUE,   -- Karnataka Government ID
    FirstName        VARCHAR(100) NOT NULL,
    EmployeeDOB      DATE,
    GenderID         INTEGER REFERENCES GenderMaster(GenderID),
    BloodGroupID     INTEGER,              -- lookup value in source doc, no table given; out of scope for analytics
    PhysicallyChallenged INTEGER CHECK (PhysicallyChallenged IN (0, 1)),
    AppointmentDate  DATE
);

CREATE TABLE Court (
    CourtID      INTEGER PRIMARY KEY AUTOINCREMENT,
    CourtName    VARCHAR(150) NOT NULL,
    DistrictID   INTEGER REFERENCES District(DistrictID),
    StateID      INTEGER REFERENCES State(StateID),
    Active       INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE CaseCategory (
    CaseCategoryID INTEGER PRIMARY KEY AUTOINCREMENT,
    LookupValue    VARCHAR(30) NOT NULL   -- FIR, UDR, Zero FIR, PAR
);

CREATE TABLE GravityOffence (
    GravityOffenceID INTEGER PRIMARY KEY AUTOINCREMENT,
    LookupValue      VARCHAR(30) NOT NULL   -- Heinous, Non-Heinous
);

CREATE TABLE CrimeHead (
    CrimeHeadID   INTEGER PRIMARY KEY AUTOINCREMENT,
    CrimeGroupName VARCHAR(100) NOT NULL,   -- e.g. Crimes Against Body
    Active        INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE CrimeSubHead (
    CrimeSubHeadID INTEGER PRIMARY KEY AUTOINCREMENT,
    CrimeHeadID    INTEGER NOT NULL REFERENCES CrimeHead(CrimeHeadID),
    CrimeHeadName  VARCHAR(100) NOT NULL,  -- e.g. Murder, Robbery (sub-head display name, per source doc)
    SeqID          INTEGER
);

CREATE TABLE Act (
    ActCode        VARCHAR(20) PRIMARY KEY,   -- e.g. IPC, NDPS
    ActDescription VARCHAR(200) NOT NULL,
    ShortName      VARCHAR(50),
    Active         INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

-- SectionCode as PK is an inference - see migration header note.
CREATE TABLE Section (
    SectionCode        VARCHAR(20) PRIMARY KEY,   -- e.g. 302, 307
    ActCode            VARCHAR(20) NOT NULL REFERENCES Act(ActCode),
    SectionDescription VARCHAR(300),
    Active             INTEGER NOT NULL DEFAULT 1 CHECK (Active IN (0, 1))
);

CREATE TABLE CrimeHeadActSection (
    CrimeHeadID  INTEGER NOT NULL REFERENCES CrimeHead(CrimeHeadID),
    ActCode      VARCHAR(20) NOT NULL REFERENCES Act(ActCode),
    SectionCode  VARCHAR(20) NOT NULL REFERENCES Section(SectionCode),
    PRIMARY KEY (CrimeHeadID, ActCode, SectionCode)
);

CREATE TABLE CasteMaster (
    caste_master_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    caste_master_name VARCHAR(100) NOT NULL
);

CREATE TABLE ReligionMaster (
    ReligionID   INTEGER PRIMARY KEY AUTOINCREMENT,
    ReligionName VARCHAR(50) NOT NULL
);

CREATE TABLE OccupationMaster (
    OccupationID   INTEGER PRIMARY KEY AUTOINCREMENT,
    OccupationName VARCHAR(100) NOT NULL
);

CREATE TABLE CaseStatusMaster (
    CaseStatusID   INTEGER PRIMARY KEY AUTOINCREMENT,
    CaseStatusName VARCHAR(50) NOT NULL   -- e.g. Under Investigation, Charge Sheeted, Closed
);

CREATE TABLE ArrestSurrenderTypeMaster (
    ArrestSurrenderTypeID INTEGER PRIMARY KEY AUTOINCREMENT,
    TypeName              VARCHAR(30) NOT NULL   -- Arrest / Voluntary Surrender
);
