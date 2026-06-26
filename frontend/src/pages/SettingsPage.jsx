import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchSettingsChannels,
  fetchSettingsChannel,
  fetchSettingsRules,
  reloadDashboardSettings,
  resetChannelSettings,
  saveChannelSettings,
} from "../api/settingsApi";

const DEFAULT_CATEGORIES = [
  { category: "flow", label: "Ροή" },
  { category: "cumulative_flow", label: "Υδρόμετρο / Σύνολο Ροής" },
  { category: "level", label: "Στάθμη" },
  { category: "quality", label: "Ποιότητα" },
  { category: "motor_current", label: "Ένταση Κινητήρα" },
  { category: "pressure", label: "Πίεση" },
  { category: "unknown", label: "Άγνωστο" },
];

const CONDITION_TYPES = [
  {
    value: "value_below_threshold",
    label: "Τιμή κάτω από όριο",
    defaultReason: "Η τιμή είναι κάτω από το όριο που έχει οριστεί.",
  },
  {
    value: "zero_value",
    label: "Μηδενική τιμή",
    defaultReason: "Η τιμή είναι μηδενική ή σχεδόν μηδενική.",
  },
  {
    value: "negative_value",
    label: "Αρνητική τιμή",
    defaultReason: "Η τιμή είναι αρνητική ενώ δεν αναμένεται.",
  },
  {
    value: "deviation_below_baseline",
    label: "Χαμηλότερη από συνήθη τιμή",
    defaultReason: "Η τιμή είναι σημαντικά χαμηλότερη από τη συνήθη τιμή.",
  },
  {
    value: "deviation_above_baseline",
    label: "Υψηλότερη από συνήθη τιμή",
    defaultReason: "Η τιμή είναι σημαντικά υψηλότερη από τη συνήθη τιμή.",
  },
  {
    value: "absolute_percent_deviation_from_baseline",
    label: "Μεγάλη απόκλιση από συνήθη τιμή",
    defaultReason: "Η τιμή αποκλίνει σημαντικά από τη συνήθη τιμή.",
  },
  {
    value: "rapid_change",
    label: "Απότομη μεταβολή",
    defaultReason: "Η τιμή μεταβλήθηκε απότομα.",
  },
  {
    value: "delta_below_min",
    label: "Πολύ μικρή μεταβολή",
    defaultReason: "Η μεταβολή είναι πολύ μικρή ή μηδενική.",
  },
  {
    value: "delta_above_max",
    label: "Υπερβολική μεταβολή",
    defaultReason: "Η μεταβολή είναι ασυνήθιστα υψηλή.",
  },
];

const METRIC_OPTIONS = [
  { value: "avg_1h", label: "Μ.Ο. 1 ώρας" },
  { value: "avg_24h", label: "Μ.Ο. 24ώρου" },
  { value: "avg_7d", label: "Μ.Ο. 7 ημερών" },
  { value: "delta_1h", label: "Μεταβολή 1 ώρας" },
  { value: "delta_24h", label: "Μεταβολή 24ώρου" },
  { value: "delta_3d", label: "Μεταβολή 3ημέρου" },
  { value: "min_24h", label: "Ελάχιστο 24ώρου" },
  { value: "max_24h", label: "Μέγιστο 24ώρου" },
];

const RULE_LABELS = {
  invalid_scada_value: "Μη έγκυρη τιμή SCADA",
  static_threshold_range: "Έλεγχος βασικών ορίων λειτουργίας",
  flow_negative_value: "Αρνητική τιμή ροής",
  flow_zero_current_value: "Μηδενική ροή",
  flow_low_vs_1h_avg: "Χαμηλή ροή σε σχέση με Μ.Ο. 1 ώρας",
  flow_low_vs_24h_avg: "Χαμηλή ροή σε σχέση με Μ.Ο. 24ώρου",
  flow_low_vs_7d_avg: "Χαμηλή ροή σε σχέση με Μ.Ο. 7 ημερών",
  flow_high_vs_24h_avg: "Υψηλή ροή σε σχέση με Μ.Ο. 24ώρου",
  cumulative_negative_delta: "Μείωση συνόλου ροής",
  cumulative_stuck_meter: "Πιθανό κολλημένο υδρόμετρο",
  cumulative_large_delta: "Υπερβολική μεταβολή υδρομέτρου",
  level_rapid_change: "Απότομη μεταβολή στάθμης",
  quality_below_60: "Χαμηλή ποιότητα",
  motor_current_high: "Υψηλή ένταση κινητήρα",
};

const RULE_DEFAULT_REASONS = {
  static_threshold_range: "Η τιμή είναι εκτός των βασικών ορίων λειτουργίας.",
  flow_zero_current_value: "Η ροή είναι μηδενική ή σχεδόν μηδενική.",
};

const RULE_PARAMS_BY_CONDITION = {
  value_below_threshold: ["warning_below", "critical_below"],
  zero_value: ["zero_epsilon"],
  negative_value: ["critical_below"],
  deviation_below_baseline: [
    "baseline",
    "min_baseline_value",
    "warning_deviation_percent",
    "critical_deviation_percent",
  ],
  deviation_above_baseline: [
    "baseline",
    "min_baseline_value",
    "warning_deviation_percent",
    "critical_deviation_percent",
  ],
  absolute_percent_deviation_from_baseline: [
    "baseline",
    "min_baseline_value",
    "warning_deviation_percent",
    "critical_deviation_percent",
  ],
  rapid_change: ["delta_field", "warning_abs_delta", "critical_abs_delta"],
  delta_below_min: ["delta_field", "warning_min_delta", "critical_min_delta"],
  delta_above_max: ["delta_field", "warning_max_delta"],
};

const RULE_PARAM_LABELS = {
  warning_below: "Προειδοποίηση όταν πέσει κάτω από",
  critical_below: "Κρίσιμο όταν πέσει κάτω από",
  zero_epsilon: "Τιμή που θεωρείται μηδενική",
  baseline: "Σύγκριση με",
  min_baseline_value: "Ελάχιστη τιμή αναφοράς",
  warning_deviation_percent: "Προειδοποίηση απόκλισης (%)",
  critical_deviation_percent: "Κρίσιμη απόκλιση (%)",
  delta_field: "Μεταβολή που ελέγχεται",
  warning_abs_delta: "Προειδοποίηση μεταβολής",
  critical_abs_delta: "Κρίσιμη μεταβολή",
  warning_min_delta: "Πολύ μικρή μεταβολή - προειδοποίηση",
  critical_min_delta: "Πολύ μικρή μεταβολή - κρίσιμο",
  warning_max_delta: "Υπερβολική μεταβολή",
};

const RULE_NUMERIC_FIELDS = [
  "zero_epsilon",
  "min_baseline_value",
  "warning_deviation_percent",
  "critical_deviation_percent",
  "warning_below",
  "critical_below",
  "warning_abs_delta",
  "critical_abs_delta",
  "warning_abs_deviation",
  "critical_abs_deviation",
  "warning_min_delta",
  "critical_min_delta",
  "warning_max_delta",
  "critical_max_delta",
];

const RULE_NUMERIC_LABELS = {
  zero_epsilon: "Zero epsilon",
  min_baseline_value: "Minimum baseline value",
  warning_deviation_percent: "Warning deviation %",
  critical_deviation_percent: "Critical deviation %",
  warning_below: "Warning below",
  critical_below: "Critical below",
  warning_abs_delta: "Warning abs delta",
  critical_abs_delta: "Critical abs delta",
  warning_abs_deviation: "Warning abs deviation",
  critical_abs_deviation: "Critical abs deviation",
  warning_min_delta: "Warning min delta",
  critical_min_delta: "Critical min delta",
  warning_max_delta: "Warning max delta",
  critical_max_delta: "Critical max delta",
};

const EMPTY_FORM = {
  zero_flow_enabled: false,
  warning_low: "",
  critical_low: "",
  warning_high: "",
  critical_high: "",
  notes: "",
};

function valueOrEmpty(value) {
  return value === null || value === undefined ? "" : String(value);
}

function boolValue(value) {
  return value === true;
}

function buildFormFromSettings(item) {
  const effective = item?.effective_config || {};
  const thresholds = effective.thresholds || {};

  return {
    zero_flow_enabled: boolValue(effective.zero_flow_enabled),
    warning_low: valueOrEmpty(thresholds.warning_low),
    critical_low: valueOrEmpty(thresholds.critical_low),
    warning_high: valueOrEmpty(thresholds.warning_high),
    critical_high: valueOrEmpty(thresholds.critical_high),
    notes: valueOrEmpty(effective.notes),
  };
}

function buildPayloadFromForm(form, ruleForms = {}) {
  const cleanText = (value) => {
    const text = String(value || "").trim();
    return text || null;
  };

  const cleanNumberText = (value) => {
    const text = String(value || "").trim().replace(",", ".");
    return text === "" ? null : text;
  };

  const disabledRules = [];
  const rules = {};
  const customRules = [];

  Object.entries(ruleForms).forEach(([ruleId, ruleForm]) => {
    const reasonText = cleanText(ruleForm.reason);
    const params = ruleForm.params || {};

    if (ruleForm.isCustom) {
      const customRule = {
        rule_id: ruleId,
        enabled: Boolean(ruleForm.enabled),
        condition_type: ruleForm.condition_type || "value_below_threshold",
        severity: ruleForm.severity || "warning",
        display_name: cleanText(ruleForm.display_name) || "Νέος έλεγχος",
        operator_reason: reasonText,
        reason_template: reasonText,
      };

      Object.entries(params).forEach(([key, value]) => {
        if (key === "baseline" || key === "delta_field") {
          customRule[key] = cleanText(value);
        } else {
          customRule[key] = cleanNumberText(value);
        }
      });

      customRules.push(customRule);
      return;
    }

    if (!ruleForm.enabled) {
      disabledRules.push(ruleId);
    }

    const ruleOverride = {
      enabled: Boolean(ruleForm.enabled),
      severity: ruleForm.severity || "warning",
      operator_reason: reasonText,
      reason_template: reasonText,
    };

    Object.entries(params).forEach(([key, value]) => {
      if (key === "baseline" || key === "delta_field") {
        ruleOverride[key] = cleanText(value);
      } else {
        ruleOverride[key] = cleanNumberText(value);
      }
    });

    rules[ruleId] = ruleOverride;
  });

  return {
    zero_flow_enabled: Boolean(form.zero_flow_enabled),
    thresholds: {
      warning_low: cleanNumberText(form.warning_low),
      critical_low: cleanNumberText(form.critical_low),
      warning_high: cleanNumberText(form.warning_high),
      critical_high: cleanNumberText(form.critical_high),
    },
    disabled_rules: disabledRules,
    rules,
    custom_rules: customRules,
    notes: cleanText(form.notes),
  };
}

function categoryLabel(category, categories) {
  return (
    categories.find((item) => item.category === category)?.label ||
    category ||
    "Άγνωστο"
  );
}

function formatOverrideStatus(item) {
  if (!item?.has_ui_override) {
    return "Default";
  }

  return item.ui_override_updated_at
    ? `Override · ${new Date(item.ui_override_updated_at).toLocaleString("el-GR")}`
    : "Override";
}

function buildRuleFormsFromRules(rules, selectedItem) {
  const effectiveConfig = selectedItem?.effective_config || {};
  const channelRuleOverrides = effectiveConfig.rules || {};
  const disabledRules = new Set(effectiveConfig.disabled_rules || []);

  const result = {};

  rules.forEach((row) => {
    const ruleId = row.rule_id;
    const effectiveRule = row.effective_rule || {};
    const channelOverride = channelRuleOverrides[ruleId] || {};
    const conditionType =
      channelOverride.condition_type ||
      effectiveRule.condition_type ||
      "value_below_threshold";

    const defaultEnabled = effectiveRule.enabled !== false;
    const overrideEnabled =
      channelOverride.enabled !== undefined
        ? Boolean(channelOverride.enabled)
        : undefined;

    const enabled =
      overrideEnabled !== undefined
        ? overrideEnabled
        : defaultEnabled && !disabledRules.has(ruleId);

    const params = makeDefaultParamsForCondition(conditionType);

    Object.keys(params).forEach((key) => {
      const value =
        channelOverride[key] ??
        effectiveRule[key] ??
        row[key];

      if (value !== undefined && value !== null) {
        params[key] = String(value);
      }
    });

    result[ruleId] = {
      isCustom: Boolean(row.is_custom),
      enabled,
      condition_type: conditionType,
      display_name:
        channelOverride.display_name ||
        effectiveRule.display_name ||
        effectiveRule.operator_label ||
        RULE_LABELS[ruleId] ||
        getConditionLabel(conditionType),
      severity:
        channelOverride.severity ||
        effectiveRule.severity ||
        row.severity ||
        "warning",
      reason:
        channelOverride.operator_reason ||
        channelOverride.reason_template ||
        RULE_DEFAULT_REASONS[ruleId] ||
        effectiveRule.operator_reason ||
        effectiveRule.reason_template ||
        row.operator_reason ||
        row.reason_template ||
        getConditionDefaultReason(conditionType),
      params,
    };
  });

  return result;
}

function getConditionLabel(conditionType) {
  return (
    CONDITION_TYPES.find((item) => item.value === conditionType)?.label ||
    conditionType ||
    "Έλεγχος"
  );
}

function getConditionDefaultReason(conditionType) {
  return (
    CONDITION_TYPES.find((item) => item.value === conditionType)?.defaultReason ||
    "Ενεργοποιήθηκε ο έλεγχος."
  );
}

function getRuleFriendlyName(rule, form) {
  const effectiveRule = rule?.effective_rule || {};
  const conditionType = form?.condition_type || effectiveRule.condition_type;

  return (
    form?.display_name ||
    effectiveRule.display_name ||
    effectiveRule.operator_label ||
    RULE_LABELS[rule?.rule_id] ||
    getConditionLabel(conditionType)
  );
}

function getParamKeysForRule(form, effectiveRule) {
  const conditionType = form?.condition_type || effectiveRule?.condition_type;
  const configuredKeys = RULE_PARAMS_BY_CONDITION[conditionType] || [];
  const existingKeys = Object.keys(form?.params || {});

  return Array.from(new Set([...configuredKeys, ...existingKeys]));
}

function getMetricLabel(value) {
  return METRIC_OPTIONS.find((item) => item.value === value)?.label || value;
}

function buildRowsFromCustomRules(customRules) {
  if (!Array.isArray(customRules)) {
    return [];
  }

  return customRules
    .filter((rule) => rule && typeof rule === "object")
    .map((rule) => ({
      rule_id: rule.rule_id,
      is_custom: true,
      effective_rule: {
        ...rule,
        enabled: rule.enabled !== false,
      },
    }));
}

function makeDefaultParamsForCondition(conditionType) {
  if (conditionType === "value_below_threshold") {
    return {
      warning_below: "",
      critical_below: "",
    };
  }

  if (conditionType === "zero_value") {
    return {
      zero_epsilon: "0.000001",
    };
  }

  if (conditionType === "negative_value") {
    return {
      critical_below: "0",
    };
  }

  if (
    conditionType === "deviation_below_baseline" ||
    conditionType === "deviation_above_baseline" ||
    conditionType === "absolute_percent_deviation_from_baseline"
  ) {
    return {
      baseline: "avg_24h",
      min_baseline_value: "0.000001",
      warning_deviation_percent: "30",
      critical_deviation_percent: "60",
    };
  }

  if (conditionType === "rapid_change") {
    return {
      delta_field: "delta_1h",
      warning_abs_delta: "",
      critical_abs_delta: "",
    };
  }

  if (conditionType === "delta_below_min") {
    return {
      delta_field: "delta_24h",
      warning_min_delta: "",
      critical_min_delta: "",
    };
  }

  if (conditionType === "delta_above_max") {
    return {
      delta_field: "delta_1h",
      warning_max_delta: "",
    };
  }

  return {};
}

function ChannelSettingsList({
  channels,
  selectedCnlNum,
  onSelect,
  categories,
}) {
  if (!channels.length) {
    return (
      <div className="settings-empty">
        Δεν βρέθηκαν κανάλια με τα τρέχοντα φίλτρα.
      </div>
    );
  }

  return (
    <div className="settings-channel-list">
      {channels.map((channel) => (
        <button
          key={channel.cnl_num}
          type="button"
          className={
            channel.cnl_num === selectedCnlNum
              ? "settings-channel-row settings-channel-row--active"
              : "settings-channel-row"
          }
          onClick={() => onSelect(channel.cnl_num)}
        >
          <span className="settings-channel-row__main">
            <strong>{channel.display_name || channel.name || "—"}</strong>
            <small>
              #{channel.cnl_num}
              {channel.installation ? ` · ${channel.installation}` : ""}
            </small>
          </span>

          <span className="settings-channel-row__meta">
            <em>{categoryLabel(channel.category, categories)}</em>
            {channel.has_ui_override ? <b>UI</b> : null}
          </span>
        </button>
      ))}
    </div>
  );
}

function ThresholdField({ label, value, onChange }) {
  return (
    <label className="settings-field">
      <span>{label}</span>
      <input
        type="text"
        inputMode="decimal"
        value={value}
        placeholder="κενό = χωρίς όριο"
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function RuleSettingsSection({
  rules,
  ruleForms,
  setRuleForms,
  onAddCustomRule,
  onRemoveCustomRule,
}) {
  return (
    <div className="settings-rules-box">
      <div className="settings-rules-header">
        <div>
          <strong>Έλεγχοι που εφαρμόζονται</strong>
          <span>Ενεργοποίησε, απενεργοποίησε ή πρόσθεσε έλεγχο για το κανάλι.</span>
        </div>

        <button
          type="button"
          className="scada-button"
          onClick={onAddCustomRule}
        >
          + Νέος έλεγχος
        </button>
      </div>

      {!rules.length ? (
        <div className="settings-empty">
          Δεν βρέθηκαν έλεγχοι για την κατηγορία αυτού του καναλιού.
        </div>
      ) : (
        <div className="settings-rule-list">
          {rules.map((rule) => {
            const ruleId = rule.rule_id;
            const effectiveRule = rule.effective_rule || {};
            const form = ruleForms[ruleId] || {
              isCustom: Boolean(rule.is_custom),
              enabled: effectiveRule.enabled !== false,
              condition_type: effectiveRule.condition_type || "value_below_threshold",
              display_name: getRuleFriendlyName(rule),
              severity: effectiveRule.severity || "warning",
              reason:
                RULE_DEFAULT_REASONS[ruleId] ||
                effectiveRule.operator_reason ||
                effectiveRule.reason_template ||
                getConditionDefaultReason(effectiveRule.condition_type),
              params: makeDefaultParamsForCondition(
                effectiveRule.condition_type || "value_below_threshold"
              ),
            };

            const paramKeys = getParamKeysForRule(form, effectiveRule);
            const validationMessage = getRuleValidationMessage(form);

            return (
              <div key={ruleId} className="settings-rule-card">
                <div className="settings-rule-card__top">
                  <label className="settings-rule-enabled">
                    <input
                      type="checkbox"
                      checked={form.enabled}
                      onChange={(event) =>
                        setRuleForms((current) => ({
                          ...current,
                          [ruleId]: {
                            ...form,
                            enabled: event.target.checked,
                          },
                        }))
                      }
                    />
                    <span>Ενεργός</span>
                  </label>

                  {form.isCustom ? (
                    <input
                      className="settings-rule-name-input"
                      type="text"
                      value={form.display_name}
                      placeholder="Όνομα ελέγχου"
                      onChange={(event) =>
                        setRuleForms((current) => ({
                          ...current,
                          [ruleId]: {
                            ...form,
                            display_name: event.target.value,
                          },
                        }))
                      }
                    />
                  ) : (
                    <strong>{getRuleFriendlyName(rule, form)}</strong>
                  )}

                  <select
                    value={form.severity}
                    onChange={(event) =>
                      setRuleForms((current) => ({
                        ...current,
                        [ruleId]: {
                          ...form,
                          severity: event.target.value,
                        },
                      }))
                    }
                  >
                    <option value="warning">Προειδοποίηση</option>
                    <option value="critical">Κρίσιμο</option>
                    <option value="unknown">Άγνωστο</option>
                  </select>
                </div>

                {form.isCustom ? (
                  <div className="settings-custom-rule-row">
                    <label className="settings-field">
                      <span>Τύπος ελέγχου</span>
                      <select
                        value={form.condition_type}
                        onChange={(event) => {
                          const nextCondition = event.target.value;
                          setRuleForms((current) => ({
                            ...current,
                            [ruleId]: {
                              ...form,
                              condition_type: nextCondition,
                              reason: getConditionDefaultReason(nextCondition),
                              params: makeDefaultParamsForCondition(nextCondition),
                            },
                          }));
                        }}
                      >
                        {CONDITION_TYPES.map((item) => (
                          <option key={item.value} value={item.value}>
                            {item.label}
                          </option>
                        ))}
                      </select>
                    </label>

                    <button
                      type="button"
                      className="scada-button settings-danger-button"
                      onClick={() => onRemoveCustomRule(ruleId)}
                    >
                      Αφαίρεση
                    </button>
                  </div>
                ) : null}

                {paramKeys.length > 0 ? (
                  <div className="settings-rule-param-grid">
                    {paramKeys.map((key) => {
                      const value = form.params?.[key] || "";

                      if (key === "baseline" || key === "delta_field") {
                        return (
                          <label key={key} className="settings-field">
                            <span>{RULE_PARAM_LABELS[key] || key}</span>
                            <select
                              value={value}
                              onChange={(event) =>
                                setRuleForms((current) => ({
                                  ...current,
                                  [ruleId]: {
                                    ...form,
                                    params: {
                                      ...(form.params || {}),
                                      [key]: event.target.value,
                                    },
                                  },
                                }))
                              }
                            >
                              {METRIC_OPTIONS.map((item) => (
                                <option key={item.value} value={item.value}>
                                  {item.label}
                                </option>
                              ))}
                            </select>
                          </label>
                        );
                      }

                      return (
                        <label key={key} className="settings-field">
                          <span>{RULE_PARAM_LABELS[key] || key}</span>
                          <input
                            type="text"
                            inputMode="decimal"
                            value={value}
                            placeholder={
                            isRequiredRuleParam(form.condition_type, key)
                                ? "Απαιτείται για ενεργό έλεγχο"
                                : "Προαιρετικό"
                            }
                            onChange={(event) =>
                              setRuleForms((current) => ({
                                ...current,
                                [ruleId]: {
                                  ...form,
                                  params: {
                                    ...(form.params || {}),
                                    [key]: event.target.value,
                                  },
                                },
                              }))
                            }
                          />
                        </label>
                      );
                    })}
                  </div>
                ) : null}

                {validationMessage ? (
                <p className="settings-rule-warning">{validationMessage}</p>
                ) : null}

                <label className="settings-field settings-field--wide">
                  <span>Μήνυμα που θα δει ο χειριστής</span>
                  <textarea
                    rows={2}
                    value={form.reason}
                    placeholder="Π.χ. Η ροή είναι κάτω από το αποδεκτό όριο."
                    onChange={(event) =>
                      setRuleForms((current) => ({
                        ...current,
                        [ruleId]: {
                          ...form,
                          reason: event.target.value,
                        },
                      }))
                    }
                  />
                </label>

                {!form.isCustom && ruleId === "static_threshold_range" ? (
                  <p className="settings-rule-note">
                    Χρησιμοποιεί τα βασικά όρια λειτουργίας που ορίζονται παραπάνω.
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function ChannelSettingsForm({
  selectedItem,
  form,
  setForm,
  rules,
  ruleForms,
  setRuleForms,
  categories,
  saving,
  onSave,
  onReset,
  onReload,
  onAddCustomRule,
  onRemoveCustomRule,
}) {
  if (!selectedItem) {
    return (
      <section className="settings-detail-panel">
        <div className="settings-empty">
          Επίλεξε κανάλι από αριστερά για να αλλάξεις όρια.
        </div>
      </section>
    );
  }

  return (
    <section className="settings-detail-panel">
      <div className="settings-detail-panel__header">
        <div>
          <h3>{selectedItem.display_name || selectedItem.name || "Κανάλι"}</h3>
          <p>
            Channel #{selectedItem.cnl_num} · {selectedItem.device_name || "χωρίς device"}
          </p>
        </div>

        <span
          className={
            selectedItem.has_ui_override
              ? "settings-override-badge settings-override-badge--active"
              : "settings-override-badge"
          }
        >
          {formatOverrideStatus(selectedItem)}
        </span>
      </div>

      <div className="settings-section-title">
        Βασικά όρια λειτουργίας
      </div>

      <p className="settings-help-text">
         Αυτές οι τιμές χρησιμοποιούνται από τον έλεγχο βασικών ορίων λειτουργίας.
         Αν η μέτρηση βγει κάτω ή πάνω από τα όρια, εμφανίζεται προειδοποίηση ή κρίσιμο alarm.
      </p>    

      <div className="settings-threshold-grid">
        <ThresholdField
          label="Χαμηλή προειδοποίηση"
          value={form.warning_low}
          onChange={(value) =>
            setForm((current) => ({
              ...current,
              warning_low: value,
            }))
          }
        />

        <ThresholdField
          label="Χαμηλό κρίσιμο όριο"
          value={form.critical_low}
          onChange={(value) =>
            setForm((current) => ({
              ...current,
              critical_low: value,
            }))
          }
        />

        <ThresholdField
          label="Υψηλή προειδοποίηση"
          value={form.warning_high}
          onChange={(value) =>
            setForm((current) => ({
              ...current,
              warning_high: value,
            }))
          }
        />

        <ThresholdField
          label="Υψηλό κρίσιμο όριο"
          value={form.critical_high}
          onChange={(value) =>
            setForm((current) => ({
              ...current,
              critical_high: value,
            }))
          }
        />
      </div>

      <div className="settings-zero-flow-box">
        <label className="settings-checkbox">
            <input
            type="checkbox"
            checked={form.zero_flow_enabled}
            onChange={(event) =>
                setForm((current) => ({
                ...current,
                zero_flow_enabled: event.target.checked,
                }))
            }
            />
            <span>Έλεγχος μηδενικής ροής</span>
        </label>

        <p>
            Αν η ροή γίνει 0 ή σχεδόν 0, θα εμφανιστεί προειδοποίηση για αυτό το κανάλι.
        </p>
        </div>

      <RuleSettingsSection
        rules={rules}
        ruleForms={ruleForms}
        setRuleForms={setRuleForms}
        onAddCustomRule={onAddCustomRule}
        onRemoveCustomRule={onRemoveCustomRule}
      />

      <label className="settings-field settings-field--wide settings-field--padded">
        <span>Σημειώσεις</span>
        <textarea
            rows={3}
            value={form.notes}
            placeholder="Προαιρετική τεχνική σημείωση για το override."
            onChange={(event) =>
            setForm((current) => ({
                ...current,
                notes: event.target.value,
            }))
            }
        />
      </label>

      <div className="settings-actions">
        <button
          type="button"
          className="scada-button scada-button--primary"
          disabled={saving}
          onClick={onSave}
        >
          {saving ? "Αποθήκευση..." : "Αποθήκευση override"}
        </button>

        <button
          type="button"
          className="scada-button"
          disabled={saving || !selectedItem.has_ui_override}
          onClick={onReset}
        >
          Επαναφορά default
        </button>

        <button
          type="button"
          className="scada-button"
          disabled={saving}
          onClick={onReload}
        >
          Καθαρισμός cache
        </button>
      </div>
    </section>
  );
}

function isBlankValue(value) {
  return String(value ?? "").trim() === "";
}

function isValidNumberText(value) {
  const text = String(value ?? "").trim().replace(",", ".");

  if (!text) {
    return true;
  }

  return Number.isFinite(Number(text));
}

function isRequiredRuleParam(conditionType, key) {
  const requiredByCondition = {
    value_below_threshold: ["warning_below", "critical_below"],
    zero_value: ["zero_epsilon"],
    negative_value: ["critical_below"],
    deviation_below_baseline: [
      "warning_deviation_percent",
      "critical_deviation_percent",
    ],
    deviation_above_baseline: [
      "warning_deviation_percent",
      "critical_deviation_percent",
    ],
    absolute_percent_deviation_from_baseline: [
      "warning_deviation_percent",
      "critical_deviation_percent",
    ],
    rapid_change: ["warning_abs_delta", "critical_abs_delta"],
    delta_below_min: ["warning_min_delta", "critical_min_delta"],
    delta_above_max: ["warning_max_delta"],
  };

  return (requiredByCondition[conditionType] || []).includes(key);
}

function getRuleValidationMessage(ruleForm) {
  if (!ruleForm?.enabled) {
    return "";
  }

  const params = ruleForm.params || {};
  const conditionType = ruleForm.condition_type;
  const name = ruleForm.display_name || "Ο έλεγχος";

  if (conditionType === "value_below_threshold") {
    if (isBlankValue(params.warning_below) && isBlankValue(params.critical_below)) {
      return `Ο έλεγχος "${name}" χρειάζεται τουλάχιστον ένα όριο.`;
    }
  }

  if (conditionType === "zero_value" && isBlankValue(params.zero_epsilon)) {
    return `Ο έλεγχος "${name}" χρειάζεται τιμή που θεωρείται μηδενική.`;
  }

  if (conditionType === "negative_value" && isBlankValue(params.critical_below)) {
    return `Ο έλεγχος "${name}" χρειάζεται όριο αρνητικής τιμής.`;
  }

  if (
    conditionType === "deviation_below_baseline" ||
    conditionType === "deviation_above_baseline" ||
    conditionType === "absolute_percent_deviation_from_baseline"
  ) {
    if (
      isBlankValue(params.warning_deviation_percent) &&
      isBlankValue(params.critical_deviation_percent)
    ) {
      return `Ο έλεγχος "${name}" χρειάζεται ποσοστό απόκλισης.`;
    }
  }

  if (conditionType === "rapid_change") {
    if (isBlankValue(params.warning_abs_delta) && isBlankValue(params.critical_abs_delta)) {
      return `Ο έλεγχος "${name}" χρειάζεται όριο μεταβολής.`;
    }
  }

  if (conditionType === "delta_below_min") {
    if (isBlankValue(params.warning_min_delta) && isBlankValue(params.critical_min_delta)) {
      return `Ο έλεγχος "${name}" χρειάζεται όριο ελάχιστης μεταβολής.`;
    }
  }

  if (conditionType === "delta_above_max" && isBlankValue(params.warning_max_delta)) {
    return `Ο έλεγχος "${name}" χρειάζεται τιμή στο πεδίο "Υπερβολική μεταβολή".`;
  }

  return "";
}

function validateRuleFormsBeforeSave(ruleForms) {
  const errors = [];

  Object.entries(ruleForms).forEach(([ruleId, ruleForm]) => {
    const params = ruleForm.params || {};
    const name = ruleForm.display_name || ruleId;

    Object.entries(params).forEach(([key, value]) => {
      if (key === "baseline" || key === "delta_field") {
        return;
      }

      if (!isValidNumberText(value)) {
        errors.push(`Το πεδίο "${RULE_PARAM_LABELS[key] || key}" στον έλεγχο "${name}" πρέπει να είναι αριθμός.`);
      }
    });

    const message = getRuleValidationMessage(ruleForm);
    if (message) {
      errors.push(message);
    }
  });

  return errors;
}

export default function SettingsPage() {
  const [channels, setChannels] = useState([]);
  const [categories, setCategories] = useState(DEFAULT_CATEGORIES);
  const [selectedCnlNum, setSelectedCnlNum] = useState(null);
  const [selectedItem, setSelectedItem] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [rules, setRules] = useState([]);
  const [ruleForms, setRuleForms] = useState({});

  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [onlyOverridden, setOnlyOverridden] = useState(false);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const loadChannels = useCallback(async () => {
    setLoading(true);
    setErrorMessage("");

    try {
      const payload = await fetchSettingsChannels({
        search: searchTerm,
        category: selectedCategory,
        onlyOverridden,
      });

      const items = Array.isArray(payload?.items) ? payload.items : [];
      setChannels(items);

      if (Array.isArray(payload?.allowed_categories)) {
        setCategories(payload.allowed_categories);
      }

      if (!selectedCnlNum && items.length > 0) {
        setSelectedCnlNum(items[0].cnl_num);
      }
    } catch (error) {
      setErrorMessage(
        error.message || "Αποτυχία φόρτωσης ρυθμίσεων καναλιών."
      );
    } finally {
      setLoading(false);
    }
  }, [searchTerm, selectedCategory, onlyOverridden, selectedCnlNum]);

  const loadSelectedChannel = useCallback(async () => {
  if (!selectedCnlNum) {
    setSelectedItem(null);
    setForm(EMPTY_FORM);
    setRules([]);
    setRuleForms({});
    return;
  }

  setErrorMessage("");

  try {
    const payload = await fetchSettingsChannel(selectedCnlNum);
    const item = payload?.item || null;

    setSelectedItem(item);
    setForm(item ? buildFormFromSettings(item) : EMPTY_FORM);

    if (item?.category) {
      const rulesPayload = await fetchSettingsRules({
        category: item.category,
      });

      const catalogRuleItems = Array.isArray(rulesPayload?.items)
    ? rulesPayload.items
    : [];

    const customRuleItems = buildRowsFromCustomRules(
    item?.effective_config?.custom_rules || []
    );

    const allRuleItems = [...catalogRuleItems, ...customRuleItems];

    setRules(allRuleItems);
    setRuleForms(buildRuleFormsFromRules(allRuleItems, item));
    } else {
      setRules([]);
      setRuleForms({});
    }
  } catch (error) {
    setErrorMessage(
      error.message || "Αποτυχία φόρτωσης ρυθμίσεων επιλεγμένου καναλιού."
    );
  }
}, [selectedCnlNum]);

  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    loadSelectedChannel();
  }, [loadSelectedChannel]);

  const filteredCountText = useMemo(() => {
    if (loading) {
      return "Φόρτωση...";
    }

    return `${channels.length} κανάλια`;
  }, [loading, channels.length]);

  async function handleSave() {
  if (!selectedCnlNum) {
    return;
  }

  setSaving(true);
  setMessage("");
  setErrorMessage("");

  const validationErrors = validateRuleFormsBeforeSave(ruleForms);

  if (validationErrors.length > 0) {
    setErrorMessage(validationErrors.join(" "));
    setSaving(false);
    return;
  }

  try {
    const payload = buildPayloadFromForm(form, ruleForms);
    await saveChannelSettings(selectedCnlNum, payload);

    setMessage("Οι ρυθμίσεις αποθηκεύτηκαν. Τα alerts θα υπολογιστούν με το νέο effective config.");
    await loadSelectedChannel();
    await loadChannels();
  } catch (error) {
    setErrorMessage(error.message || "Αποτυχία αποθήκευσης ρυθμίσεων.");
  } finally {
    setSaving(false);
  }
}

  async function handleReset() {
    if (!selectedCnlNum) {
      return;
    }

    const confirmed = window.confirm(
      "Να αφαιρεθεί το UI override και να επιστρέψει το κανάλι στο default config;"
    );

    if (!confirmed) {
      return;
    }

    setSaving(true);
    setMessage("");
    setErrorMessage("");

    try {
      await resetChannelSettings(selectedCnlNum);

      setMessage("Το override αφαιρέθηκε. Το κανάλι επέστρεψε στο default config.");
      await loadSelectedChannel();
      await loadChannels();
    } catch (error) {
      setErrorMessage(error.message || "Αποτυχία επαναφοράς default config.");
    } finally {
      setSaving(false);
    }
  }

  async function handleReload() {
    setSaving(true);
    setMessage("");
    setErrorMessage("");

    try {
      await reloadDashboardSettings();
      setMessage("Η cache καθαρίστηκε. Στην επόμενη ανανέωση θα εφαρμοστούν τα νέα settings.");
    } catch (error) {
      setErrorMessage(error.message || "Αποτυχία καθαρισμού cache.");
    } finally {
      setSaving(false);
    }
  }

  function handleAddCustomRule() {
  if (!selectedCnlNum) {
    return;
  }

  const conditionType = "value_below_threshold";
  const ruleId = `custom_${selectedCnlNum}_${Date.now()}`;

  const newRule = {
    rule_id: ruleId,
    is_custom: true,
    effective_rule: {
      rule_id: ruleId,
      enabled: true,
      condition_type: conditionType,
      severity: "warning",
      display_name: "Νέος έλεγχος",
      operator_reason: getConditionDefaultReason(conditionType),
      reason_template: getConditionDefaultReason(conditionType),
    },
  };

  setRules((current) => [...current, newRule]);
  setRuleForms((current) => ({
    ...current,
    [ruleId]: {
      isCustom: true,
      enabled: true,
      condition_type: conditionType,
      display_name: "Νέος έλεγχος",
      severity: "warning",
      reason: getConditionDefaultReason(conditionType),
      params: makeDefaultParamsForCondition(conditionType),
    },
  }));
}

function handleRemoveCustomRule(ruleId) {
  const confirmed = window.confirm("Να αφαιρεθεί αυτός ο νέος έλεγχος από το κανάλι;");

  if (!confirmed) {
    return;
  }

  setRules((current) => current.filter((rule) => rule.rule_id !== ruleId));
  setRuleForms((current) => {
    const next = { ...current };
    delete next[ruleId];
    return next;
  });
}

  return (
    <section className="page page--scada settings-page">
      <div className="scada-page-title">
        <div>
          <h2>Ρυθμίσεις Ορίων</h2>
          <p>Τοπικά UI overrides πάνω στα JSON configs · όχι αλλαγές στο Rapid SCADA</p>
        </div>

        <div className="settings-toolbar">
          <label htmlFor="settings-search">Αναζήτηση</label>
          <input
            id="settings-search"
            type="search"
            value={searchTerm}
            placeholder="Κανάλι, εγκατάσταση, tag..."
            onChange={(event) => setSearchTerm(event.target.value)}
          />
        </div>
      </div>

      <section className="settings-filter-bar">
        <label>
          <span>Κατηγορία</span>
          <select
            value={selectedCategory}
            onChange={(event) => {
              setSelectedCategory(event.target.value);
              setSelectedCnlNum(null);
            }}
          >
            <option value="all">Όλες οι κατηγορίες</option>
            {categories.map((item) => (
              <option key={item.category} value={item.category}>
                {item.label}
              </option>
            ))}
          </select>
        </label>

        <label className="settings-checkbox settings-checkbox--compact">
          <input
            type="checkbox"
            checked={onlyOverridden}
            onChange={(event) => {
              setOnlyOverridden(event.target.checked);
              setSelectedCnlNum(null);
            }}
          />
          <span>Μόνο κανάλια με UI override</span>
        </label>

        <strong>{filteredCountText}</strong>
      </section>

      {errorMessage && (
        <div className="state-box state-box--error">
          <strong>Σφάλμα</strong>
          <span>{errorMessage}</span>
        </div>
      )}

      {message && (
        <div className="state-box state-box--loading">
          <strong>OK</strong>
          <span>{message}</span>
        </div>
      )}

      <div className="settings-layout">
        <section className="settings-list-panel">
          <div className="settings-list-panel__header">
            <h3>Κανάλια</h3>
            <span>{channels.length}</span>
          </div>

          {loading ? (
            <div className="settings-empty">Φόρτωση καναλιών...</div>
          ) : (
            <ChannelSettingsList
              channels={channels}
              selectedCnlNum={selectedCnlNum}
              onSelect={setSelectedCnlNum}
              categories={categories}
            />
          )}
        </section>

        <ChannelSettingsForm
            selectedItem={selectedItem}
            form={form}
            setForm={setForm}
            rules={rules}
            ruleForms={ruleForms}
            setRuleForms={setRuleForms}
            categories={categories}
            saving={saving}
            onSave={handleSave}
            onReset={handleReset}
            onReload={handleReload}
            onAddCustomRule={handleAddCustomRule}
            onRemoveCustomRule={handleRemoveCustomRule}
            />
      </div>
    </section>
  );
}