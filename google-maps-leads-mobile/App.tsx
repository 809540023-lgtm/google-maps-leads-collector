import { MaterialCommunityIcons } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  Linking,
  Platform,
  Pressable,
  SafeAreaView,
  ScrollView,
  Share,
  StyleSheet,
  StyleProp,
  Switch,
  Text,
  TextInput,
  View,
  ViewStyle
} from "react-native";

import { LeadsApi } from "./src/api";
import { colors } from "./src/theme";
import { CreateJobPayload, Lead, LeadStatus, Metrics, ScrapeJob } from "./src/types";

declare const process: {
  env: {
    EXPO_PUBLIC_API_BASE_URL?: string;
    EXPO_PUBLIC_ANDROID_DOWNLOAD_URL?: string;
    EXPO_PUBLIC_IOS_DOWNLOAD_URL?: string;
    EXPO_PUBLIC_RELEASES_URL?: string;
  };
};

type TabKey = "dashboard" | "leads" | "jobs" | "settings";
type StatusFilter = "" | LeadStatus;

const ENV_API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL;
const DEFAULT_API_BASE =
  ENV_API_BASE && ENV_API_BASE.trim()
    ? ENV_API_BASE.trim()
    : Platform.OS === "android"
      ? "http://10.0.2.2:8000"
      : "http://127.0.0.1:8000";
const ANDROID_DOWNLOAD_URL = process.env.EXPO_PUBLIC_ANDROID_DOWNLOAD_URL?.trim();
const IOS_DOWNLOAD_URL = process.env.EXPO_PUBLIC_IOS_DOWNLOAD_URL?.trim();
const RELEASES_URL =
  process.env.EXPO_PUBLIC_RELEASES_URL?.trim() ||
  "https://github.com/emily77/google-maps-leads-collector/releases";
const DEFAULT_TERMS = ["工廠", "公司", "倉儲", "物流", "辦公室", "汽車維修", "診所", "店家"].join("\n");
const EMPTY_METRICS: Metrics = {
  total: 0,
  with_phone: 0,
  with_email: 0,
  contacted: 0,
  qualified: 0,
  grade_a: 0,
  grade_b: 0,
  jobs: 0
};

const tabs: Array<{ key: TabKey; label: string; icon: keyof typeof MaterialCommunityIcons.glyphMap }> = [
  { key: "dashboard", label: "總覽", icon: "view-dashboard-outline" },
  { key: "leads", label: "名單", icon: "card-account-phone-outline" },
  { key: "jobs", label: "任務", icon: "map-marker-radius-outline" },
  { key: "settings", label: "設定", icon: "cog-outline" }
];

const statusOptions: Array<{ value: StatusFilter; label: string }> = [
  { value: "", label: "全部" },
  { value: "new", label: "新資料" },
  { value: "contacted", label: "已聯絡" },
  { value: "qualified", label: "可追蹤" },
  { value: "invalid", label: "無效" }
];

const statusLabels: Record<LeadStatus, string> = {
  new: "新資料",
  contacted: "已聯絡",
  qualified: "可追蹤",
  invalid: "無效"
};

const statusColors: Record<LeadStatus, string> = {
  new: colors.warn,
  contacted: colors.accent2,
  qualified: colors.accent,
  invalid: colors.danger
};

type JobForm = {
  query: string;
  address: string;
  location: string;
  search_mode: "grid" | "radius" | "simple";
  query_terms: string;
  radius_m: string;
  max_distance_m: string;
  grid_cell_km: string;
  zoom: string;
  lang: string;
  depth: string;
  concurrency: string;
  extract_email: boolean;
  strict_distance_filter: boolean;
  notes: string;
};

const defaultJobForm: JobForm = {
  query: "全球商家電話收集",
  address: "新北市泰山區楓江路40-2號",
  location: "新北市泰山區楓江路",
  search_mode: "grid",
  query_terms: DEFAULT_TERMS,
  radius_m: "3000",
  max_distance_m: "5000",
  grid_cell_km: "0.4",
  zoom: "16",
  lang: "zh-TW",
  depth: "10",
  concurrency: "4",
  extract_email: true,
  strict_distance_filter: true,
  notes: ""
};

const asNumber = (value: string, fallback: number) => {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
};

const distanceText = (lead: Lead) => {
  if (lead.distance_m == null) return lead.distance_band || "未分級";
  return `${lead.distance_band || "距離"} · ${Math.round(lead.distance_m)}m`;
};

const endpointForMaps = (lead: Lead) => {
  if (lead.google_maps_url) return lead.google_maps_url;
  if (lead.latitude != null && lead.longitude != null) {
    return `https://www.google.com/maps/search/?api=1&query=${lead.latitude},${lead.longitude}`;
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(lead.address || lead.name)}`;
};

export default function App() {
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE);
  const [draftApiBase, setDraftApiBase] = useState(DEFAULT_API_BASE);
  const [activeTab, setActiveTab] = useState<TabKey>("dashboard");
  const [metrics, setMetrics] = useState<Metrics>(EMPTY_METRICS);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [jobs, setJobs] = useState<ScrapeJob[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("");
  const [phoneOnly, setPhoneOnly] = useState(true);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [jobForm, setJobForm] = useState<JobForm>(defaultJobForm);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextMetrics, nextJobs, nextLeads] = await Promise.all([
        LeadsApi.metrics(apiBase),
        LeadsApi.jobs(apiBase),
        LeadsApi.leads(apiBase, { q: query, status: statusFilter, phoneOnly })
      ]);
      setMetrics(nextMetrics);
      setJobs(nextJobs);
      setLeads(nextLeads);
    } catch (err) {
      setError(err instanceof Error ? err.message : "連線失敗");
    } finally {
      setLoading(false);
    }
  }, [apiBase, phoneOnly, query, statusFilter]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const latestJob = jobs[0];
  const conversionRate = useMemo(() => {
    if (!metrics.total) return "0%";
    return `${Math.round((metrics.with_phone / metrics.total) * 100)}%`;
  }, [metrics.total, metrics.with_phone]);

  const updateLeadStatus = async (lead: Lead, status: LeadStatus) => {
    setSaving(true);
    setError("");
    try {
      const updated = await LeadsApi.updateLeadStatus(apiBase, lead.id, status);
      setLeads((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      setMetrics(await LeadsApi.metrics(apiBase));
    } catch (err) {
      setError(err instanceof Error ? err.message : "狀態更新失敗");
    } finally {
      setSaving(false);
    }
  };

  const createJob = async () => {
    const payload: CreateJobPayload = {
      query: jobForm.query.trim() || "Google Maps leads",
      address: jobForm.address.trim(),
      location: jobForm.location.trim(),
      search_mode: jobForm.search_mode,
      query_terms: jobForm.query_terms
        .split(/\n|,|，/)
        .map((item) => item.trim())
        .filter(Boolean),
      radius_m: asNumber(jobForm.radius_m, 3000),
      max_distance_m: asNumber(jobForm.max_distance_m, 5000),
      grid_cell_km: asNumber(jobForm.grid_cell_km, 0.4),
      zoom: asNumber(jobForm.zoom, 16),
      lang: jobForm.lang.trim() || "zh-TW",
      concurrency: asNumber(jobForm.concurrency, 4),
      max_results: 50,
      depth: asNumber(jobForm.depth, 10),
      extract_email: jobForm.extract_email,
      strict_distance_filter: jobForm.strict_distance_filter,
      notes: jobForm.notes.trim()
    };

    setSaving(true);
    setError("");
    try {
      const job = await LeadsApi.createJob(apiBase, payload);
      setJobs((items) => [job, ...items]);
      setMetrics(await LeadsApi.metrics(apiBase));
      setActiveTab("jobs");
    } catch (err) {
      setError(err instanceof Error ? err.message : "建立任務失敗");
    } finally {
      setSaving(false);
    }
  };

  const openUrl = async (url: string) => {
    const supported = await Linking.canOpenURL(url);
    if (supported) {
      await Linking.openURL(url);
    } else {
      Alert.alert("無法開啟", url);
    }
  };

  const renderDashboard = () => (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <View>
          <Text style={styles.eyebrow}>Google Maps Leads</Text>
          <Text style={styles.title}>全球電話收集 App</Text>
        </View>
        <Pressable style={styles.iconButton} onPress={loadData}>
          {loading ? (
            <ActivityIndicator color={colors.accent} />
          ) : (
            <MaterialCommunityIcons name="refresh" size={22} color={colors.accent} />
          )}
        </Pressable>
      </View>

      <View style={styles.metricGrid}>
        <MetricCard label="總資料" value={metrics.total} icon="database-outline" />
        <MetricCard label="有效電話" value={metrics.with_phone} icon="phone-check-outline" />
        <MetricCard label="A 級" value={metrics.grade_a} icon="star-outline" />
        <MetricCard label="電話率" value={conversionRate} icon="chart-donut" />
      </View>

      <View style={styles.panel}>
        <Text style={styles.sectionTitle}>最新任務</Text>
        {latestJob ? (
          <JobSummary job={latestJob} onShare={() => void Share.share({ message: latestJob.command })} />
        ) : (
          <Text style={styles.muted}>尚未建立任務</Text>
        )}
      </View>

      <View style={styles.actionRow}>
        <ActionButton icon="download-outline" label="CSV" onPress={() => void openUrl(LeadsApi.exportCsvUrl(apiBase, true))} />
        <ActionButton icon="web" label="Web" onPress={() => void openUrl(LeadsApi.webUrl(apiBase))} />
        <ActionButton icon="map-marker-plus-outline" label="新任務" onPress={() => setActiveTab("jobs")} />
      </View>
    </ScrollView>
  );

  const renderLeads = () => (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.sectionHeader}>
        <Text style={styles.titleSmall}>名單</Text>
        <Pressable style={styles.iconButton} onPress={loadData}>
          <MaterialCommunityIcons name="refresh" size={22} color={colors.accent} />
        </Pressable>
      </View>
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="搜尋名稱、電話、地址、分類"
        placeholderTextColor={colors.muted}
        style={styles.input}
      />
      <Segmented
        value={statusFilter}
        options={statusOptions}
        onChange={(value) => setStatusFilter(value as StatusFilter)}
      />
      <View style={styles.switchRow}>
        <Text style={styles.switchLabel}>只看有效電話</Text>
        <Switch value={phoneOnly} onValueChange={setPhoneOnly} trackColor={{ true: colors.accent, false: colors.line }} />
      </View>

      <Text style={styles.listCount}>{leads.length} 筆</Text>
      {leads.map((lead) => (
        <LeadCard
          key={lead.id}
          lead={lead}
          disabled={saving}
          onCall={() => void openUrl(`tel:${lead.normalized_phone || lead.phone}`)}
          onMap={() => void openUrl(endpointForMaps(lead))}
          onWebsite={() => lead.website && void openUrl(lead.website)}
          onStatus={(status) => void updateLeadStatus(lead, status)}
        />
      ))}
    </ScrollView>
  );

  const renderJobs = () => (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.titleSmall}>建立任務</Text>
      <View style={styles.panel}>
        <TextField label="任務名稱" value={jobForm.query} onChangeText={(queryText) => setJobForm({ ...jobForm, query: queryText })} />
        <TextField label="中心地點 / 地址 / 座標 / Maps URL" value={jobForm.address} onChangeText={(address) => setJobForm({ ...jobForm, address })} />
        <TextField label="搜尋地區文字" value={jobForm.location} onChangeText={(location) => setJobForm({ ...jobForm, location })} />
        <Segmented
          value={jobForm.search_mode}
          options={[
            { value: "grid", label: "網格" },
            { value: "radius", label: "半徑" },
            { value: "simple", label: "文字" }
          ]}
          onChange={(searchMode) => setJobForm({ ...jobForm, search_mode: searchMode as JobForm["search_mode"] })}
        />
        <TextField label="queries.txt" value={jobForm.query_terms} multiline onChangeText={(queryTerms) => setJobForm({ ...jobForm, query_terms: queryTerms })} />
        <View style={styles.twoCols}>
          <TextField containerStyle={styles.colField} label="半徑 m" value={jobForm.radius_m} keyboardType="number-pad" onChangeText={(radius) => setJobForm({ ...jobForm, radius_m: radius })} />
          <TextField containerStyle={styles.colField} label="保留距離 m" value={jobForm.max_distance_m} keyboardType="number-pad" onChangeText={(distance) => setJobForm({ ...jobForm, max_distance_m: distance })} />
        </View>
        <View style={styles.twoCols}>
          <TextField containerStyle={styles.colField} label="Grid km" value={jobForm.grid_cell_km} keyboardType="decimal-pad" onChangeText={(cell) => setJobForm({ ...jobForm, grid_cell_km: cell })} />
          <TextField containerStyle={styles.colField} label="Depth" value={jobForm.depth} keyboardType="number-pad" onChangeText={(depth) => setJobForm({ ...jobForm, depth })} />
        </View>
        <View style={styles.twoCols}>
          <TextField containerStyle={styles.colField} label="Lang" value={jobForm.lang} onChangeText={(lang) => setJobForm({ ...jobForm, lang })} />
          <TextField containerStyle={styles.colField} label="併發" value={jobForm.concurrency} keyboardType="number-pad" onChangeText={(concurrency) => setJobForm({ ...jobForm, concurrency })} />
        </View>
        <View style={styles.switchRow}>
          <Text style={styles.switchLabel}>抓 Email</Text>
          <Switch value={jobForm.extract_email} onValueChange={(extractEmail) => setJobForm({ ...jobForm, extract_email: extractEmail })} />
        </View>
        <View style={styles.switchRow}>
          <Text style={styles.switchLabel}>距離過濾</Text>
          <Switch value={jobForm.strict_distance_filter} onValueChange={(strictDistance) => setJobForm({ ...jobForm, strict_distance_filter: strictDistance })} />
        </View>
        <PrimaryButton label={saving ? "建立中" : "建立任務"} icon="plus-circle-outline" disabled={saving} onPress={() => void createJob()} />
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.titleSmall}>任務列表</Text>
        <Text style={styles.listCount}>{jobs.length} 筆</Text>
      </View>
      {jobs.map((job) => (
        <View key={job.id} style={styles.panel}>
          <JobSummary job={job} onShare={() => void Share.share({ message: `${job.queries_text}\n\n${job.command}` })} />
        </View>
      ))}
    </ScrollView>
  );

  const renderSettings = () => (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.titleSmall}>設定</Text>
      <View style={styles.panel}>
        <TextField label="API Base URL" value={draftApiBase} autoCapitalize="none" onChangeText={setDraftApiBase} />
        <PrimaryButton
          label="套用 API"
          icon="check-circle-outline"
          onPress={() => {
            setApiBase(draftApiBase.trim() || DEFAULT_API_BASE);
            setActiveTab("dashboard");
          }}
        />
        <ActionButton icon="restore" label="重設本機" onPress={() => setDraftApiBase(DEFAULT_API_BASE)} />
      </View>
      <View style={styles.panel}>
        <Text style={styles.sectionTitle}>目前連線</Text>
        <Text style={styles.mono}>{apiBase}</Text>
        <Text style={styles.muted}>iOS/Web 本機通常使用 127.0.0.1；Android emulator 使用 10.0.2.2；實機可改成 Render 或區網位址。</Text>
      </View>
      <View style={styles.panel}>
        <Text style={styles.sectionTitle}>App 下載</Text>
        <Text style={styles.muted}>Android 會使用 APK 或 Play 測試連結；iOS 會使用 TestFlight、Ad Hoc 或模擬器 build 連結。</Text>
        <View style={styles.downloadGrid}>
          {IOS_DOWNLOAD_URL ? (
            <ActionButton icon="apple" label="iOS" onPress={() => void openUrl(IOS_DOWNLOAD_URL)} />
          ) : (
            <DownloadPlaceholder icon="apple" label="iOS" text="等待 TestFlight / Ad Hoc build" />
          )}
          {ANDROID_DOWNLOAD_URL ? (
            <ActionButton icon="android" label="Android" onPress={() => void openUrl(ANDROID_DOWNLOAD_URL)} />
          ) : (
            <DownloadPlaceholder icon="android" label="Android" text="等待 APK build" />
          )}
          <ActionButton icon="github" label="Releases" onPress={() => void openUrl(RELEASES_URL)} />
        </View>
      </View>
    </ScrollView>
  );

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      <View style={styles.appBar}>
        <View style={styles.logoMark}>
          <MaterialCommunityIcons name="map-search-outline" size={22} color="#fff" />
        </View>
        <View style={styles.appBarText}>
          <Text style={styles.appName}>Leads Collector</Text>
          <Text style={styles.appSub} numberOfLines={1}>{apiBase}</Text>
        </View>
      </View>

      {error ? (
        <Pressable style={styles.errorBox} onPress={() => setError("")}>
          <MaterialCommunityIcons name="alert-circle-outline" size={18} color={colors.danger} />
          <Text style={styles.errorText} numberOfLines={2}>{error}</Text>
        </Pressable>
      ) : null}

      <View style={styles.screen}>
        {activeTab === "dashboard" && renderDashboard()}
        {activeTab === "leads" && renderLeads()}
        {activeTab === "jobs" && renderJobs()}
        {activeTab === "settings" && renderSettings()}
      </View>

      <View style={styles.tabBar}>
        {tabs.map((tab) => {
          const selected = activeTab === tab.key;
          return (
            <Pressable key={tab.key} style={styles.tabButton} onPress={() => setActiveTab(tab.key)}>
              <MaterialCommunityIcons name={tab.icon} size={22} color={selected ? colors.accent : colors.muted} />
              <Text style={[styles.tabLabel, selected && styles.tabLabelActive]}>{tab.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </SafeAreaView>
  );
}

function MetricCard({ label, value, icon }: { label: string; value: string | number; icon: keyof typeof MaterialCommunityIcons.glyphMap }) {
  return (
    <View style={styles.metricCard}>
      <View style={styles.metricIcon}>
        <MaterialCommunityIcons name={icon} size={20} color={colors.accent} />
      </View>
      <Text style={styles.metricValue}>{value}</Text>
      <Text style={styles.metricLabel}>{label}</Text>
    </View>
  );
}

function TextField({
  label,
  value,
  onChangeText,
  multiline,
  keyboardType,
  autoCapitalize,
  containerStyle
}: {
  label: string;
  value: string;
  onChangeText: (value: string) => void;
  multiline?: boolean;
  keyboardType?: "default" | "number-pad" | "decimal-pad";
  autoCapitalize?: "none" | "sentences" | "words" | "characters";
  containerStyle?: StyleProp<ViewStyle>;
}) {
  return (
    <View style={[styles.field, containerStyle]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      <TextInput
        value={value}
        onChangeText={onChangeText}
        multiline={multiline}
        keyboardType={keyboardType}
        autoCapitalize={autoCapitalize}
        placeholderTextColor={colors.muted}
        style={[styles.input, multiline && styles.textArea]}
      />
    </View>
  );
}

function Segmented({
  value,
  options,
  onChange
}: {
  value: string;
  options: Array<{ value: string; label: string }>;
  onChange: (value: string) => void;
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.segmented}>
      {options.map((option) => {
        const selected = option.value === value;
        return (
          <Pressable key={option.value || "all"} style={[styles.segment, selected && styles.segmentActive]} onPress={() => onChange(option.value)}>
            <Text style={[styles.segmentText, selected && styles.segmentTextActive]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

function PrimaryButton({
  label,
  icon,
  onPress,
  disabled
}: {
  label: string;
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable style={[styles.primaryButton, disabled && styles.disabledButton]} onPress={onPress} disabled={disabled}>
      <MaterialCommunityIcons name={icon} size={19} color="#fff" />
      <Text style={styles.primaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function ActionButton({
  label,
  icon,
  onPress
}: {
  label: string;
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  onPress: () => void;
}) {
  return (
    <Pressable style={styles.secondaryButton} onPress={onPress}>
      <MaterialCommunityIcons name={icon} size={19} color={colors.accent} />
      <Text style={styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function DownloadPlaceholder({
  label,
  icon,
  text
}: {
  label: string;
  icon: keyof typeof MaterialCommunityIcons.glyphMap;
  text: string;
}) {
  return (
    <View style={styles.downloadPlaceholder}>
      <MaterialCommunityIcons name={icon} size={19} color={colors.muted} />
      <View style={styles.downloadTextWrap}>
        <Text style={styles.downloadLabel}>{label}</Text>
        <Text style={styles.downloadText}>{text}</Text>
      </View>
    </View>
  );
}

function LeadCard({
  lead,
  disabled,
  onCall,
  onMap,
  onWebsite,
  onStatus
}: {
  lead: Lead;
  disabled: boolean;
  onCall: () => void;
  onMap: () => void;
  onWebsite: () => void;
  onStatus: (status: LeadStatus) => void;
}) {
  return (
    <View style={styles.leadCard}>
      <View style={styles.leadTop}>
        <View style={styles.leadTitleWrap}>
          <Text style={styles.leadName} numberOfLines={2}>{lead.name}</Text>
          <Text style={styles.leadMeta} numberOfLines={1}>{lead.category || "未分類"} · {distanceText(lead)}</Text>
        </View>
        <View style={[styles.gradeBadge, lead.lead_grade === "A" && styles.gradeBadgeA]}>
          <Text style={styles.gradeText}>{lead.lead_grade || "-"}</Text>
        </View>
      </View>
      <Text style={styles.phone}>{lead.phone || "-"}</Text>
      <Text style={styles.address} numberOfLines={2}>{lead.address || "無地址"}</Text>
      <View style={styles.leadActions}>
        {lead.phone ? <ActionButton icon="phone-outline" label="撥打" onPress={onCall} /> : null}
        <ActionButton icon="map-marker-outline" label="地圖" onPress={onMap} />
        {lead.website ? <ActionButton icon="web" label="網站" onPress={onWebsite} /> : null}
      </View>
      <View style={styles.statusRow}>
        {(Object.keys(statusLabels) as LeadStatus[]).map((status) => {
          const selected = lead.status === status;
          return (
            <Pressable
              key={status}
              disabled={disabled}
              style={[styles.statusChip, selected && { borderColor: statusColors[status], backgroundColor: colors.soft }]}
              onPress={() => onStatus(status)}
            >
              <Text style={[styles.statusText, selected && { color: statusColors[status] }]}>{statusLabels[status]}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

function JobSummary({ job, onShare }: { job: ScrapeJob; onShare: () => void }) {
  const center = job.center_latitude != null && job.center_longitude != null
    ? `${job.center_latitude.toFixed(6)}, ${job.center_longitude.toFixed(6)}`
    : "未解析";
  return (
    <View>
      <View style={styles.jobTop}>
        <View style={styles.leadTitleWrap}>
          <Text style={styles.jobTitle} numberOfLines={2}>{job.query}</Text>
          <Text style={styles.leadMeta}>{job.search_mode} · {job.geocode_status || "not_needed"} · imported {job.imported_count}</Text>
        </View>
        <Pressable style={styles.iconButton} onPress={onShare}>
          <MaterialCommunityIcons name="share-outline" size={20} color={colors.accent} />
        </Pressable>
      </View>
      <Text style={styles.muted}>{job.location || job.address || "無地區文字"}</Text>
      <Text style={styles.mono}>{center}</Text>
      {job.grid_bbox ? <Text style={styles.mono}>bbox {job.grid_bbox}</Text> : null}
      <Text style={styles.command} numberOfLines={5}>{job.command}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  safe: {
    flex: 1,
    backgroundColor: colors.bg
  },
  appBar: {
    minHeight: 70,
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.line,
    backgroundColor: colors.panel,
    flexDirection: "row",
    alignItems: "center"
  },
  logoMark: {
    width: 42,
    height: 42,
    borderRadius: 8,
    backgroundColor: colors.accent,
    alignItems: "center",
    justifyContent: "center",
    marginRight: 12
  },
  appBarText: {
    flex: 1,
    minWidth: 0
  },
  appName: {
    fontSize: 18,
    fontWeight: "800",
    color: colors.ink
  },
  appSub: {
    marginTop: 2,
    fontSize: 12,
    color: colors.muted
  },
  screen: {
    flex: 1
  },
  content: {
    padding: 16,
    paddingBottom: 110
  },
  hero: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 14
  },
  eyebrow: {
    color: colors.accent,
    fontWeight: "800",
    fontSize: 13
  },
  title: {
    color: colors.ink,
    fontSize: 30,
    lineHeight: 36,
    fontWeight: "900"
  },
  titleSmall: {
    color: colors.ink,
    fontSize: 24,
    lineHeight: 30,
    fontWeight: "900",
    marginBottom: 12
  },
  metricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 10,
    marginBottom: 14
  },
  metricCard: {
    flexBasis: "47%",
    flexGrow: 1,
    minHeight: 118,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    padding: 14
  },
  metricIcon: {
    width: 34,
    height: 34,
    borderRadius: 8,
    backgroundColor: colors.soft,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10
  },
  metricValue: {
    color: colors.ink,
    fontSize: 28,
    fontWeight: "900"
  },
  metricLabel: {
    color: colors.muted,
    fontWeight: "700",
    marginTop: 4
  },
  panel: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    padding: 14,
    marginBottom: 14
  },
  sectionTitle: {
    color: colors.ink,
    fontSize: 18,
    fontWeight: "800",
    marginBottom: 10
  },
  sectionHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10
  },
  actionRow: {
    flexDirection: "row",
    gap: 9,
    flexWrap: "wrap"
  },
  downloadGrid: {
    flexDirection: "row",
    gap: 9,
    flexWrap: "wrap",
    marginTop: 12
  },
  downloadPlaceholder: {
    minHeight: 48,
    minWidth: 138,
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.bg,
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  downloadTextWrap: {
    flex: 1,
    minWidth: 0
  },
  downloadLabel: {
    color: colors.ink,
    fontWeight: "800"
  },
  downloadText: {
    color: colors.muted,
    fontSize: 11,
    marginTop: 2
  },
  iconButton: {
    width: 42,
    height: 42,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    alignItems: "center",
    justifyContent: "center"
  },
  input: {
    minHeight: 44,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: "#fff",
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: colors.ink,
    fontSize: 15,
    marginBottom: 10
  },
  textArea: {
    minHeight: 118,
    textAlignVertical: "top"
  },
  field: {
    marginBottom: 2
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    marginBottom: 6
  },
  segmented: {
    gap: 8,
    paddingBottom: 10
  },
  segment: {
    minHeight: 38,
    paddingHorizontal: 13,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    justifyContent: "center"
  },
  segmentActive: {
    borderColor: colors.accent,
    backgroundColor: colors.soft
  },
  segmentText: {
    color: colors.muted,
    fontWeight: "700"
  },
  segmentTextActive: {
    color: colors.accent
  },
  switchRow: {
    minHeight: 46,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    paddingHorizontal: 12,
    marginBottom: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between"
  },
  switchLabel: {
    color: colors.ink,
    fontWeight: "800"
  },
  listCount: {
    color: colors.muted,
    fontWeight: "800",
    marginBottom: 10
  },
  leadCard: {
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    padding: 14,
    marginBottom: 12
  },
  leadTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10
  },
  leadTitleWrap: {
    flex: 1,
    minWidth: 0
  },
  leadName: {
    color: colors.ink,
    fontSize: 18,
    lineHeight: 23,
    fontWeight: "800"
  },
  leadMeta: {
    color: colors.muted,
    marginTop: 4,
    fontSize: 13,
    fontWeight: "600"
  },
  gradeBadge: {
    minWidth: 38,
    height: 34,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    alignItems: "center",
    justifyContent: "center"
  },
  gradeBadgeA: {
    backgroundColor: colors.soft,
    borderColor: colors.accent
  },
  gradeText: {
    color: colors.accent,
    fontWeight: "900"
  },
  phone: {
    color: colors.ink,
    fontSize: 17,
    fontWeight: "800",
    marginTop: 10
  },
  address: {
    color: colors.muted,
    lineHeight: 20,
    marginTop: 6
  },
  leadActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginTop: 12
  },
  statusRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 7,
    marginTop: 12
  },
  statusChip: {
    minHeight: 32,
    paddingHorizontal: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    justifyContent: "center"
  },
  statusText: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800"
  },
  secondaryButton: {
    minHeight: 40,
    paddingHorizontal: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    flexDirection: "row",
    alignItems: "center",
    gap: 7
  },
  secondaryButtonText: {
    color: colors.accent,
    fontWeight: "800"
  },
  primaryButton: {
    minHeight: 46,
    borderRadius: 8,
    backgroundColor: colors.accent,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 14,
    marginTop: 6
  },
  disabledButton: {
    opacity: 0.6
  },
  primaryButtonText: {
    color: "#fff",
    fontSize: 15,
    fontWeight: "800"
  },
  twoCols: {
    flexDirection: "row",
    gap: 10
  },
  colField: {
    flex: 1,
    minWidth: 0
  },
  jobTop: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 10,
    marginBottom: 8
  },
  jobTitle: {
    color: colors.ink,
    fontSize: 17,
    lineHeight: 23,
    fontWeight: "800"
  },
  muted: {
    color: colors.muted,
    lineHeight: 20
  },
  mono: {
    color: colors.ink,
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" }),
    fontSize: 12,
    marginTop: 8
  },
  command: {
    color: colors.muted,
    fontFamily: Platform.select({ ios: "Menlo", android: "monospace", default: "monospace" }),
    fontSize: 12,
    lineHeight: 17,
    marginTop: 10,
    padding: 10,
    borderRadius: 8,
    backgroundColor: colors.bg
  },
  errorBox: {
    margin: 12,
    marginBottom: 0,
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#e3b6b6",
    backgroundColor: "#fff5f5",
    flexDirection: "row",
    alignItems: "center",
    gap: 8
  },
  errorText: {
    flex: 1,
    color: colors.danger,
    fontWeight: "700"
  },
  tabBar: {
    minHeight: 70,
    borderTopWidth: 1,
    borderTopColor: colors.line,
    backgroundColor: colors.panel,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-around",
    paddingBottom: 4
  },
  tabButton: {
    minWidth: 68,
    minHeight: 56,
    alignItems: "center",
    justifyContent: "center",
    gap: 3
  },
  tabLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800"
  },
  tabLabelActive: {
    color: colors.accent
  }
});
