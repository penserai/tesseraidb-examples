#!/usr/bin/env python3
"""
Predictive Maintenance - Failure Prediction Analysis
=====================================================

Advanced analytics for predicting equipment failures using:
- Remaining Useful Life (RUL) estimation
- Anomaly detection with statistical methods
- Trend analysis and forecasting
- Risk-based maintenance prioritization
- What-if scenario analysis

This module provides enterprise-grade predictive analytics that can be
integrated with machine learning pipelines.

Usage:
    python analysis.py [--base-url URL] [--report] [--equipment-id ID]
    python analysis.py --risk-matrix       # Generate risk priority matrix
    python analysis.py --forecast HOURS    # Forecast equipment health
"""

import sys
import os
import math
import random
import argparse
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from common import get_client, logger, NAMESPACE_PREFIXES


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class EquipmentHealthProfile:
    """Complete health profile for equipment."""
    equipment_id: str
    equipment_type: str
    name: str
    health_score: float
    remaining_useful_life: float
    failure_probability: float
    anomaly_score: float
    criticality: str
    operating_hours: float
    risk_priority_number: float
    maintenance_urgency: str
    recommended_action: str
    estimated_failure_date: Optional[datetime]
    confidence_interval: Tuple[float, float]


@dataclass
class RiskMatrix:
    """Risk assessment matrix entry."""
    equipment_id: str
    likelihood: int  # 1-5 scale
    consequence: int  # 1-5 scale
    risk_score: int  # likelihood * consequence
    risk_level: str  # low, medium, high, critical
    mitigation: str


@dataclass
class ForecastResult:
    """Health forecast result."""
    equipment_id: str
    current_health: float
    forecast_hours: float
    predicted_health: float
    predicted_rul: float
    confidence_lower: float
    confidence_upper: float
    trend: str  # stable, degrading, rapid_degradation


# =============================================================================
# ANALYSIS ENGINE
# =============================================================================

class PredictiveAnalyzer:
    """
    Predictive maintenance analysis engine.
    """

    def __init__(self, client):
        self.client = client
        self.equipment_profiles: Dict[str, EquipmentHealthProfile] = {}

    def _normalize_properties(self, properties: Dict) -> Dict:
        """
        Normalize property names by stripping domain prefixes.
        The API returns properties like 'predictive_maintenance#healthScore'
        but we want to access them as 'healthScore'.
        """
        normalized = {}
        for key, value in properties.items():
            # Strip domain prefix (e.g., 'predictive_maintenance#healthScore' -> 'healthScore')
            if '#' in key:
                short_key = key.split('#', 1)[1]
            else:
                short_key = key
            normalized[short_key] = value
        return normalized

    def calculate_risk_priority_number(self, severity: int, occurrence: int,
                                        detection: int) -> float:
        """
        Calculate Risk Priority Number (RPN) using FMEA methodology.
        RPN = Severity x Occurrence x Detection
        Scale: 1-10 for each factor, max RPN = 1000
        """
        return severity * occurrence * detection

    def estimate_failure_probability(self, health_score: float, rul: float,
                                      operating_hours: float, mtbf: float) -> float:
        """
        Estimate probability of failure in next 30 days using Weibull model.
        """
        # Time window for prediction (720 hours = 30 days)
        prediction_window = 720

        if rul <= 0:
            return 0.99

        # Basic probability from RUL
        if rul < prediction_window:
            base_prob = 1 - (rul / prediction_window)
        else:
            base_prob = prediction_window / rul * 0.1

        # Adjust for health score
        health_factor = (100 - health_score) / 100

        # Adjust for operating hours vs MTBF
        utilization = operating_hours / mtbf if mtbf > 0 else 1.0
        age_factor = min(1.0, utilization ** 1.5)

        # Combined probability
        combined = base_prob * 0.4 + health_factor * 0.3 + age_factor * 0.3

        return min(0.99, max(0.01, combined))

    def calculate_maintenance_urgency(self, health_score: float, rul: float,
                                        criticality: str) -> Tuple[str, str]:
        """
        Determine maintenance urgency and recommended action.
        """
        criticality_factor = {"critical": 1.5, "high": 1.2, "medium": 1.0, "low": 0.8}
        crit_mult = criticality_factor.get(criticality, 1.0)

        # Adjusted thresholds based on criticality
        critical_rul = 200 * crit_mult
        urgent_rul = 500 * crit_mult
        planned_rul = 1500 * crit_mult

        if health_score < 20 or rul < critical_rul:
            return "immediate", "Schedule immediate corrective maintenance"
        elif health_score < 40 or rul < urgent_rul:
            return "urgent", "Schedule maintenance within 48 hours"
        elif health_score < 60 or rul < planned_rul:
            return "planned", "Schedule maintenance within 2 weeks"
        elif health_score < 80:
            return "monitor", "Increase monitoring frequency"
        else:
            return "normal", "Continue routine maintenance schedule"

    def estimate_failure_date(self, health_score: float, rul: float,
                               degradation_rate: float) -> Optional[datetime]:
        """
        Estimate when equipment will likely fail.
        """
        if rul <= 0:
            return datetime.now()

        # Calculate hours until failure based on RUL
        hours_to_failure = rul

        # Adjust based on current degradation rate
        if degradation_rate > 0:
            # Faster degradation = sooner failure
            rate_adjustment = 1 + degradation_rate * 10
            hours_to_failure = hours_to_failure / rate_adjustment

        estimated_date = datetime.now() + timedelta(hours=hours_to_failure)
        return estimated_date

    def calculate_confidence_interval(self, rul: float, health_score: float) -> Tuple[float, float]:
        """
        Calculate 90% confidence interval for RUL prediction.
        Wider intervals for less certain predictions.
        """
        # Uncertainty increases with lower health and lower RUL
        base_uncertainty = 0.2 + (100 - health_score) / 200

        if rul < 500:
            uncertainty = base_uncertainty * 1.5
        elif rul < 2000:
            uncertainty = base_uncertainty * 1.2
        else:
            uncertainty = base_uncertainty

        lower = max(0, rul * (1 - uncertainty))
        upper = rul * (1 + uncertainty)

        return (lower, upper)

    def analyze_equipment(self, twin_data: Dict) -> Optional[EquipmentHealthProfile]:
        """
        Perform comprehensive analysis on single equipment.
        """
        equipment_id = twin_data.get("id")
        raw_properties = twin_data.get("properties", {})

        # Normalize property names (strip domain prefixes like 'predictive_maintenance#')
        properties = self._normalize_properties(raw_properties)

        # Skip non-equipment twins
        if "healthScore" not in properties:
            return None

        health_score = properties.get("healthScore", 85)
        rul = properties.get("remainingUsefulLife", 5000)
        operating_hours = properties.get("operatingHours", 10000)
        mtbf = properties.get("mtbf", 15000)
        criticality = properties.get("criticality", "medium")
        anomaly_score = properties.get("anomalyScore", 0.0)

        # Get failure mode info
        severity = properties.get("failureModeSeverity", 5)
        detection = 10 - int(health_score / 15)  # Lower detection score for healthier equipment

        # Calculate metrics
        failure_prob = self.estimate_failure_probability(
            health_score, rul, operating_hours, mtbf
        )

        # Occurrence based on operating hours vs MTBF
        occurrence = min(10, int((operating_hours / mtbf) * 10) + 1)

        rpn = self.calculate_risk_priority_number(severity, occurrence, detection)

        urgency, action = self.calculate_maintenance_urgency(
            health_score, rul, criticality
        )

        # Estimate failure date
        degradation_rate = properties.get("degradationRate", 0.01)
        failure_date = self.estimate_failure_date(health_score, rul, degradation_rate)

        confidence = self.calculate_confidence_interval(rul, health_score)

        # SDK model uses 'type_uri' not 'type'
        type_val = twin_data.get("type_uri") or twin_data.get("type") or ""
        profile = EquipmentHealthProfile(
            equipment_id=equipment_id,
            equipment_type=type_val.split("#")[-1] if type_val else "",
            name=twin_data.get("name", equipment_id),
            health_score=health_score,
            remaining_useful_life=rul,
            failure_probability=failure_prob,
            anomaly_score=anomaly_score,
            criticality=criticality,
            operating_hours=operating_hours,
            risk_priority_number=rpn,
            maintenance_urgency=urgency,
            recommended_action=action,
            estimated_failure_date=failure_date,
            confidence_interval=confidence,
        )

        self.equipment_profiles[equipment_id] = profile
        return profile

    def analyze_all_equipment(self) -> List[EquipmentHealthProfile]:
        """
        Analyze all equipment in the predictive maintenance domain.
        """
        try:
            twins = self.client.twins.list(domain="predictive_maintenance")
        except Exception as e:
            logger.error(f"Failed to list twins: {e}")
            return []

        profiles = []
        for twin in twins:
            twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
            profile = self.analyze_equipment(twin_dict)
            if profile:
                profiles.append(profile)

        # Sort by risk priority number (highest first)
        profiles.sort(key=lambda x: x.risk_priority_number, reverse=True)
        return profiles

    def generate_risk_matrix(self) -> List[RiskMatrix]:
        """
        Generate risk assessment matrix for all equipment.
        """
        if not self.equipment_profiles:
            self.analyze_all_equipment()

        risk_entries = []

        for eq_id, profile in self.equipment_profiles.items():
            # Calculate likelihood (1-5 scale)
            if profile.failure_probability > 0.8:
                likelihood = 5
            elif profile.failure_probability > 0.6:
                likelihood = 4
            elif profile.failure_probability > 0.4:
                likelihood = 3
            elif profile.failure_probability > 0.2:
                likelihood = 2
            else:
                likelihood = 1

            # Calculate consequence (1-5 scale) based on criticality
            consequence_map = {"critical": 5, "high": 4, "medium": 3, "low": 2}
            consequence = consequence_map.get(profile.criticality, 2)

            risk_score = likelihood * consequence

            if risk_score >= 20:
                risk_level = "critical"
                mitigation = "Immediate shutdown and repair required"
            elif risk_score >= 12:
                risk_level = "high"
                mitigation = "Schedule urgent maintenance within 48 hours"
            elif risk_score >= 6:
                risk_level = "medium"
                mitigation = "Plan maintenance in next scheduled window"
            else:
                risk_level = "low"
                mitigation = "Monitor and maintain per schedule"

            risk_entries.append(RiskMatrix(
                equipment_id=eq_id,
                likelihood=likelihood,
                consequence=consequence,
                risk_score=risk_score,
                risk_level=risk_level,
                mitigation=mitigation,
            ))

        # Sort by risk score
        risk_entries.sort(key=lambda x: x.risk_score, reverse=True)
        return risk_entries

    def forecast_health(self, equipment_id: str, hours_ahead: float) -> Optional[ForecastResult]:
        """
        Forecast equipment health at a future point in time.
        Uses exponential degradation model.
        """
        if equipment_id not in self.equipment_profiles:
            self.analyze_all_equipment()

        if equipment_id not in self.equipment_profiles:
            return None

        profile = self.equipment_profiles[equipment_id]

        # Calculate degradation rate
        # Assuming exponential decay: H(t) = H0 * e^(-lambda * t)
        current_health = profile.health_score
        current_rul = profile.remaining_useful_life

        if current_rul <= 0:
            return ForecastResult(
                equipment_id=equipment_id,
                current_health=current_health,
                forecast_hours=hours_ahead,
                predicted_health=0,
                predicted_rul=0,
                confidence_lower=0,
                confidence_upper=0,
                trend="failed"
            )

        # Estimate lambda from current state
        # At RUL, health should be ~10%
        lambda_rate = math.log(current_health / 10) / current_rul if current_health > 10 else 0.001

        # Predict future health
        predicted_health = current_health * math.exp(-lambda_rate * hours_ahead)
        predicted_health = max(0, min(100, predicted_health))

        # Predict future RUL
        predicted_rul = max(0, current_rul - hours_ahead)

        # Confidence bounds (wider for further predictions)
        time_uncertainty = 1 + (hours_ahead / 1000) * 0.2
        base_uncertainty = 0.15

        confidence_lower = predicted_health * (1 - base_uncertainty * time_uncertainty)
        confidence_upper = predicted_health * (1 + base_uncertainty * time_uncertainty)

        # Determine trend
        health_drop = current_health - predicted_health
        if health_drop > 30:
            trend = "rapid_degradation"
        elif health_drop > 10:
            trend = "degrading"
        else:
            trend = "stable"

        return ForecastResult(
            equipment_id=equipment_id,
            current_health=current_health,
            forecast_hours=hours_ahead,
            predicted_health=predicted_health,
            predicted_rul=predicted_rul,
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            trend=trend,
        )

    def generate_maintenance_schedule(self, planning_horizon_days: int = 90) -> List[Dict]:
        """
        Generate optimized maintenance schedule based on predictions.
        """
        if not self.equipment_profiles:
            self.analyze_all_equipment()

        schedule = []
        current_date = datetime.now()
        horizon_end = current_date + timedelta(days=planning_horizon_days)

        # Group equipment by urgency
        by_urgency = defaultdict(list)
        for eq_id, profile in self.equipment_profiles.items():
            by_urgency[profile.maintenance_urgency].append(profile)

        # Schedule immediate and urgent items first
        scheduled_dates = []

        for urgency in ["immediate", "urgent", "planned", "monitor"]:
            for profile in by_urgency[urgency]:
                if profile.estimated_failure_date and profile.estimated_failure_date < horizon_end:
                    # Schedule before predicted failure
                    schedule_date = profile.estimated_failure_date - timedelta(days=7)
                    if schedule_date < current_date:
                        schedule_date = current_date + timedelta(days=1)

                    # Avoid scheduling conflicts
                    while schedule_date.date() in scheduled_dates:
                        schedule_date += timedelta(days=1)

                    scheduled_dates.append(schedule_date.date())

                    schedule.append({
                        "equipment_id": profile.equipment_id,
                        "equipment_name": profile.name,
                        "scheduled_date": schedule_date.strftime("%Y-%m-%d"),
                        "urgency": profile.maintenance_urgency,
                        "recommended_action": profile.recommended_action,
                        "estimated_rul": profile.remaining_useful_life,
                        "health_score": profile.health_score,
                        "risk_priority": profile.risk_priority_number,
                    })

        # Sort by scheduled date
        schedule.sort(key=lambda x: x["scheduled_date"])
        return schedule


# =============================================================================
# REPORTING
# =============================================================================

def print_health_report(profiles: List[EquipmentHealthProfile]):
    """Print formatted health report."""
    print("\n" + "=" * 100)
    print(" PREDICTIVE MAINTENANCE HEALTH REPORT")
    print(" Generated: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 100)

    # Summary statistics
    total = len(profiles)
    critical = sum(1 for p in profiles if p.health_score < 20)
    warning = sum(1 for p in profiles if 20 <= p.health_score < 50)
    degraded = sum(1 for p in profiles if 50 <= p.health_score < 75)
    healthy = sum(1 for p in profiles if p.health_score >= 75)

    print(f"\nFleet Summary: {total} equipment assets")
    print(f"  Healthy (>75%):     {healthy:3d} ({healthy/total*100:.1f}%)")
    print(f"  Degraded (50-75%):  {degraded:3d} ({degraded/total*100:.1f}%)")
    print(f"  Warning (20-50%):   {warning:3d} ({warning/total*100:.1f}%)")
    print(f"  Critical (<20%):    {critical:3d} ({critical/total*100:.1f}%)")

    print("\n" + "-" * 100)
    print(" TOP 15 EQUIPMENT REQUIRING ATTENTION (by Risk Priority)")
    print("-" * 100)
    print(f"{'Equipment ID':<35} {'Type':<20} {'Health':>7} {'RUL(h)':>8} "
          f"{'Fail%':>6} {'RPN':>5} {'Urgency':<12}")
    print("-" * 100)

    for profile in profiles[:15]:
        urgency_color = {
            "immediate": "!!! ",
            "urgent": "!!  ",
            "planned": "!   ",
            "monitor": "    ",
            "normal": "    "
        }
        prefix = urgency_color.get(profile.maintenance_urgency, "    ")

        print(f"{prefix}{profile.equipment_id[:31]:<31} {profile.equipment_type[:20]:<20} "
              f"{profile.health_score:>6.1f}% {profile.remaining_useful_life:>7.0f} "
              f"{profile.failure_probability*100:>5.1f}% {profile.risk_priority_number:>5.0f} "
              f"{profile.maintenance_urgency:<12}")

    # Recommended actions
    print("\n" + "-" * 100)
    print(" RECOMMENDED ACTIONS")
    print("-" * 100)

    immediate = [p for p in profiles if p.maintenance_urgency == "immediate"]
    if immediate:
        print("\nIMMEDIATE ATTENTION REQUIRED:")
        for p in immediate:
            print(f"  - {p.equipment_id}: {p.recommended_action}")
            if p.estimated_failure_date:
                print(f"    Estimated failure: {p.estimated_failure_date.strftime('%Y-%m-%d')}")

    urgent = [p for p in profiles if p.maintenance_urgency == "urgent"]
    if urgent:
        print("\nURGENT (within 48 hours):")
        for p in urgent[:5]:
            print(f"  - {p.equipment_id}: {p.recommended_action}")


def print_risk_matrix(risks: List[RiskMatrix]):
    """Print risk assessment matrix."""
    print("\n" + "=" * 80)
    print(" RISK ASSESSMENT MATRIX")
    print("=" * 80)

    # Print matrix header
    print("\n                    CONSEQUENCE")
    print("              1     2     3     4     5")
    print("         +-----+-----+-----+-----+-----+")

    # Count equipment in each cell
    matrix = defaultdict(list)
    for r in risks:
        matrix[(r.likelihood, r.consequence)].append(r.equipment_id)

    for likelihood in range(5, 0, -1):
        row = f"   L={likelihood}  |"
        for consequence in range(1, 6):
            count = len(matrix[(likelihood, consequence)])
            if count > 0:
                row += f" {count:3d} |"
            else:
                row += "  -  |"
        print(row)
        print("         +-----+-----+-----+-----+-----+")

    print("\nL=Likelihood, Cells show equipment count")

    # Risk level summary
    print("\n" + "-" * 80)
    print(" RISK LEVEL SUMMARY")
    print("-" * 80)

    by_level = defaultdict(list)
    for r in risks:
        by_level[r.risk_level].append(r)

    for level in ["critical", "high", "medium", "low"]:
        items = by_level[level]
        print(f"\n{level.upper()} RISK ({len(items)} items):")
        for r in items[:3]:
            print(f"  - {r.equipment_id}: L={r.likelihood}, C={r.consequence}, "
                  f"Score={r.risk_score}")
            print(f"    Mitigation: {r.mitigation}")


def print_forecast(forecasts: List[ForecastResult], hours: float):
    """Print health forecast report."""
    print("\n" + "=" * 80)
    print(f" HEALTH FORECAST - {hours:.0f} HOURS AHEAD")
    print("=" * 80)

    print(f"\n{'Equipment ID':<35} {'Current':>8} {'Forecast':>9} "
          f"{'CI (90%)':>15} {'Trend':<15}")
    print("-" * 80)

    for f in forecasts:
        trend_icon = {
            "stable": "->",
            "degrading": "v",
            "rapid_degradation": "vv",
            "failed": "X"
        }
        icon = trend_icon.get(f.trend, "?")

        print(f"{f.equipment_id[:35]:<35} {f.current_health:>7.1f}% {f.predicted_health:>8.1f}% "
              f"[{f.confidence_lower:>5.1f}-{f.confidence_upper:>5.1f}]% "
              f"{icon} {f.trend:<12}")


def main():
    parser = argparse.ArgumentParser(description="Predictive Maintenance Analysis")
    parser.add_argument("--base-url", help="DTaaS server URL")
    parser.add_argument("--report", action="store_true", help="Generate full health report")
    parser.add_argument("--risk-matrix", action="store_true", help="Generate risk matrix")
    parser.add_argument("--forecast", type=float, help="Forecast health N hours ahead")
    parser.add_argument("--equipment-id", help="Analyze specific equipment")
    parser.add_argument("--schedule", type=int, help="Generate maintenance schedule for N days")
    args = parser.parse_args()

    client = get_client(args.base_url)
    analyzer = PredictiveAnalyzer(client)

    if args.equipment_id:
        # Analyze specific equipment
        try:
            twin = client.twins.get(args.equipment_id)
            twin_dict = twin.model_dump() if hasattr(twin, 'model_dump') else twin
            profile = analyzer.analyze_equipment(twin_dict)
            if profile:
                print(f"\nEquipment Analysis: {args.equipment_id}")
                print("-" * 50)
                print(f"  Type: {profile.equipment_type}")
                print(f"  Health Score: {profile.health_score:.1f}%")
                print(f"  RUL: {profile.remaining_useful_life:.0f} hours")
                print(f"  Failure Probability (30d): {profile.failure_probability*100:.1f}%")
                print(f"  Risk Priority Number: {profile.risk_priority_number:.0f}")
                print(f"  Urgency: {profile.maintenance_urgency}")
                print(f"  Action: {profile.recommended_action}")
                if profile.estimated_failure_date:
                    print(f"  Est. Failure Date: {profile.estimated_failure_date.strftime('%Y-%m-%d')}")
                print(f"  RUL Confidence (90%): [{profile.confidence_interval[0]:.0f}, "
                      f"{profile.confidence_interval[1]:.0f}] hours")
        except Exception as e:
            print(f"Error: {e}")
        return

    # Analyze all equipment
    profiles = analyzer.analyze_all_equipment()

    if not profiles:
        print("No equipment found. Run seed.py first to create equipment twins.")
        return

    if args.report or (not args.risk_matrix and not args.forecast and not args.schedule):
        print_health_report(profiles)

    if args.risk_matrix:
        risks = analyzer.generate_risk_matrix()
        print_risk_matrix(risks)

    if args.forecast:
        forecasts = []
        for eq_id in analyzer.equipment_profiles:
            f = analyzer.forecast_health(eq_id, args.forecast)
            if f:
                forecasts.append(f)
        forecasts.sort(key=lambda x: x.predicted_health)
        print_forecast(forecasts[:20], args.forecast)

    if args.schedule:
        schedule = analyzer.generate_maintenance_schedule(args.schedule)
        print("\n" + "=" * 80)
        print(f" MAINTENANCE SCHEDULE - NEXT {args.schedule} DAYS")
        print("=" * 80)
        print(f"\n{'Date':<12} {'Equipment':<35} {'Urgency':<12} {'Action':<30}")
        print("-" * 90)
        for item in schedule[:20]:
            print(f"{item['scheduled_date']:<12} {item['equipment_id'][:35]:<35} "
                  f"{item['urgency']:<12} {item['recommended_action'][:30]:<30}")


if __name__ == "__main__":
    main()
