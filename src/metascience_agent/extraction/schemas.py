"""Pydantic schemas for extracted statistics and analysis results."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    """Severity levels for findings."""
    IMPOSSIBLE = "impossible"  # Violates arithmetic, probability, GRIM/GRIMMER
    HIGHLY_SUSPICIOUS = "highly_suspicious"  # p-value clustering, SD/SE confusion
    SUSPICIOUS = "suspicious"  # Unusual but technically possible
    INDETERMINATE = "indeterminate"  # Can't determine
    CONSISTENT = "consistent"  # Passes checks


class Location(BaseModel):
    """Location of a statistic within a paper."""
    page: Optional[int] = None
    section: Optional[str] = None
    table: Optional[int] = None
    row: Optional[int] = None
    column: Optional[int] = None
    context: Optional[str] = Field(None, description="Surrounding text for context")


class GroupStatistics(BaseModel):
    """Statistics for a single group."""
    n: int = Field(..., description="Sample size")
    mean: float = Field(..., description="Mean value")
    sd: Optional[float] = Field(None, description="Standard deviation")
    se: Optional[float] = Field(None, description="Standard error")
    median: Optional[float] = None
    min_val: Optional[float] = Field(None, alias="min")
    max_val: Optional[float] = Field(None, alias="max")

    class Config:
        populate_by_name = True


class TTestData(BaseModel):
    """Data for an independent or paired t-test."""
    test_type: str = Field("independent", description="'independent' or 'paired'")
    group1: GroupStatistics
    group2: GroupStatistics
    reported_t: Optional[float] = None
    reported_df: Optional[int] = None
    reported_p: Optional[float] = None
    location: Optional[Location] = None


class ANOVAData(BaseModel):
    """Data for a one-way ANOVA."""
    groups: list[GroupStatistics] = Field(..., min_length=2)
    reported_f: Optional[float] = None
    reported_df_between: Optional[int] = None
    reported_df_within: Optional[int] = None
    reported_p: Optional[float] = None
    location: Optional[Location] = None


class ChiSquaredData(BaseModel):
    """Data for a chi-squared test."""
    observed: list[list[int]] = Field(..., description="2D contingency table")
    reported_chi2: Optional[float] = None
    reported_df: Optional[int] = None
    reported_p: Optional[float] = None
    test_type: str = Field("pearson", description="'pearson', 'yates', or 'fisher'")
    location: Optional[Location] = None


class RegressionData(BaseModel):
    """Data for a regression coefficient."""
    b: float = Field(..., description="Unstandardized coefficient")
    se: float = Field(..., description="Standard error")
    reported_t: Optional[float] = None
    reported_p: Optional[float] = None
    df: Optional[int] = None
    location: Optional[Location] = None


class PercentageData(BaseModel):
    """Data for percentage/proportion checks."""
    percentages: list[float] = Field(..., description="List of percentages")
    n: int = Field(..., description="Sample size")
    should_sum_to: float = Field(100.0, description="Expected sum (usually 100)")
    location: Optional[Location] = None


class MeanData(BaseModel):
    """Data for GRIM/GRIMMER checks on means."""
    mean: float
    sd: Optional[float] = None
    n: int
    scale_min: int = Field(..., description="Minimum value on scale (e.g., 1 for Likert)")
    scale_max: int = Field(..., description="Maximum value on scale (e.g., 7 for Likert)")
    decimals: int = Field(2, description="Number of decimal places reported")
    location: Optional[Location] = None


class ExtractedStatistic(BaseModel):
    """Generic container for any extracted statistic."""
    stat_type: str = Field(..., description="Type: t_test, anova, chi_squared, etc.")
    raw_text: str = Field(..., description="Original text from paper")
    data: dict = Field(..., description="Parsed data (type-specific)")
    location: Optional[Location] = None


class Finding(BaseModel):
    """A single finding from analysis."""
    technique: str = Field(..., description="Name of technique used")
    severity: Severity
    description: str = Field(..., description="Human-readable description")
    expected: Optional[str] = Field(None, description="What was expected")
    observed: Optional[str] = Field(None, description="What was observed")
    location: Optional[Location] = None
    inputs: dict = Field(default_factory=dict, description="Inputs to the analysis")
    methodology: str = Field("", description="How to reproduce this finding")


class AnalysisReport(BaseModel):
    """Complete analysis report for a paper."""
    title: Optional[str] = None
    authors: Optional[list[str]] = None
    journal: Optional[str] = None
    year: Optional[int] = None
    doi: Optional[str] = None

    # Analysis results
    findings: list[Finding] = Field(default_factory=list)
    statistics_checked: int = Field(0, description="Total statistics examined")
    techniques_used: list[str] = Field(default_factory=list)

    # Raw extractions for verification
    extracted_statistics: list[ExtractedStatistic] = Field(default_factory=list)

    # Overall assessment
    overall_severity: Optional[Severity] = None
    summary: str = Field("", description="Executive summary")
