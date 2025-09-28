import { useState, useEffect, useMemo } from 'react';
import { useError } from '../context/ErrorContext';
import { useAuth } from '../context/AuthContext';
import { formatDisplayValue, isNumericValue } from '../utils/numberUtils';
import {
  fetchSensorData,
  SensorData,
  listDevices,
  Device,
  fetchPartitions,
  NormalizationRule,
  listNormalizationRules,
  ComputationDef,
  listComputations,
  registerDevice,
  toggleDevice,
  deleteDevice,
  setBufferMaxRows,
} from '../api/backendRequests';
import { reportClientError } from '../errors';

export const usePipelineData = () => {
  const { setError } = useError();
  const { username } = useAuth();
  
  // Shared state for pipeline data
  const [activePartition, setActivePartition] = useState<string>('');
  const [partitions, setPartitions] = useState<string[]>([]);
  
  // Sensor data state
  const [sensorData, setSensorData] = useState<SensorData[]>([]);
  const [devices, setDevices] = useState<Device[]>([]);
  const [bufferSize, setBufferSize] = useState<number>(100);
  const [viewMode, setViewMode] = useState<'table' | 'json'>('json');
  
  // Device registration state
  const [ingestionId, setIngestionId] = useState<string>('');
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  
  // Normalization rules state
  const [normalizationRules, setNormalizationRules] = useState<NormalizationRule[]>([]);
  
  // Computations state
  const [computations, setComputations] = useState<ComputationDef[]>([]);
  
  // Load all pipeline data
  const loadPipelineData = async () => {
    try {
      const [parts, rules, comps] = await Promise.all([
        fetchPartitions(),
        listNormalizationRules(),
        listComputations(),
      ]);
      
      setPartitions(parts);
      setNormalizationRules(rules);
      setComputations(comps || []); // Ensure it's always an array
    } catch (err) {
      console.error('Error loading pipeline data:', err);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  // Load sensor data and devices for selected partition
  const loadSensorData = async () => {
    try {
      const [sensorData, deviceData] = await Promise.all([
        fetchSensorData(activePartition || undefined),
        listDevices(),
      ]);
      
      setSensorData(sensorData);
      setDevices(deviceData);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    loadPipelineData();
  }, []);

  useEffect(() => {
    loadSensorData();
    const interval = setInterval(loadSensorData, 5000);
    return () => clearInterval(interval);
  }, [activePartition, setError]);

  // Filter rules and computations by active partition
  const filteredRules = normalizationRules.filter(rule => 
    !activePartition || rule.ingestion_id === activePartition || !rule.ingestion_id
  );
  
  const relatedComputations = computations.filter(comp => 
    // Show computations that might be related to the current partition
    !activePartition || 
    comp.description?.toLowerCase().includes(activePartition.toLowerCase()) ||
    comp.name.toLowerCase().includes(activePartition.toLowerCase())
  );

  const handlePartitionChange = (partition: string) => {
    setActivePartition(partition);
    // Auto-fill ingestion ID and name when selecting a partition
    if (partition) {
      setIngestionId(partition);
      setName(partition);
    }
  };

  const handleDataRefresh = () => {
    loadSensorData();
    loadPipelineData();
  };

  const applyBufferSize = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await setBufferMaxRows(Math.max(1, bufferSize));
    } catch (err) {
      console.error('Error setting buffer size:', err);
    }
  };

  const handleRegisterDevice = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username) {
      setError('You must be authenticated to register a device.');
      return;
    }
    try {
      await registerDevice({
        ingestion_id: ingestionId,
        name,
        description,
        enabled: true,
        created_by: username,
      });
      setIngestionId('');
      setName('');
      setDescription('');
      loadSensorData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      reportClientError({ message: String(err), severity: 'error', component: 'DataPipelinePage', context: 'registerDevice' }).catch(() => {});
    }
  };

  const handleToggleDevice = async (id: number) => {
    try {
      await toggleDevice(id);
      loadSensorData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      reportClientError({ message: String(err), severity: 'error', component: 'DataPipelinePage', context: 'toggleDevice' }).catch(() => {});
    }
  };

  const handleDeleteDevice = async (id: number) => {
    try {
      await deleteDevice(id);
      loadSensorData();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      reportClientError({ message: String(err), severity: 'error', component: 'DataPipelinePage', context: 'deleteDevice' }).catch(() => {});
    }
  };

  // Build table columns dynamically from incoming data
  const tableColumns: string[] = useMemo(() => {
    const keys = new Set<string>();
    for (const row of sensorData) {
      Object.keys(row as Record<string, unknown>).forEach((k) => keys.add(k));
    }
    // Prefer common keys first
    const preferred = ['timestamp', 'time', 'sensorId', 'sensor-id', 'sensor_id', 'temperature', 'humidity', 'ingestion_id'];
    const ordered: string[] = [];
    for (const p of preferred) if (keys.has(p)) ordered.push(p);
    for (const k of Array.from(keys)) if (!ordered.includes(k)) ordered.push(k);
    return ordered.slice(0, 12); // cap to 12 columns for readability
  }, [sensorData]);

  const renderValue = (v: unknown) => {
    if (v === null || v === undefined) return '-';
    if (typeof v === 'object') return JSON.stringify(v);
    
    // Format numeric values to 2 decimal places for consistent display
    if (isNumericValue(v)) {
      return formatDisplayValue(v);
    }
    
    const s = String(v);
    return s.length > 80 ? s.slice(0, 77) + '…' : s;
  };

  return {
    // State
    activePartition,
    partitions,
    sensorData,
    devices,
    bufferSize,
    viewMode,
    ingestionId,
    name,
    description,
    normalizationRules,
    computations,
    filteredRules,
    relatedComputations,
    tableColumns,
    
    // Setters
    setActivePartition: handlePartitionChange,
    setBufferSize,
    setViewMode,
    setIngestionId,
    setName,
    setDescription,
    
    // Handlers
    handleDataRefresh,
    applyBufferSize,
    handleRegisterDevice,
    handleToggleDevice,
    handleDeleteDevice,
    loadPipelineData,
    renderValue,
  };
};
