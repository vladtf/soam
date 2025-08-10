import React, { useEffect, useState } from 'react';
import { Button, Card } from 'react-bootstrap';
import PageHeader from '../components/PageHeader';
import { useTheme } from '../context/ThemeContext';
import {
  ComputationDef,
  createComputation,
  deleteComputation,
  listComputations,
  previewComputation,
  updateComputation,
  fetchComputationExamples,
  ComputationExample,
  fetchComputationSchemas,
} from '../api/backendRequests';
import ComputationsTable from '../components/computations/ComputationsTable';
import EditorModal from '../components/computations/EditorModal';
import PreviewModal from '../components/computations/PreviewModal';

const empty: ComputationDef = { name: '', dataset: 'silver', definition: {}, description: '', enabled: true };

const ComputationsPage: React.FC = () => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [items, setItems] = useState<ComputationDef[]>([]);
  const [loading, setLoading] = useState(false);
  const [show, setShow] = useState(false);
  const [editing, setEditing] = useState<ComputationDef | null>(null);
  const [previewData, setPreviewData] = useState<unknown[] | null>(null);
  const [previewOpen, setPreviewOpen] = useState<boolean>(false);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [sources, setSources] = useState<string[]>([]);
  const [examples, setExamples] = useState<ComputationExample[]>([]);
  const [dslOps, setDslOps] = useState<string[]>([]);
  const [schemas, setSchemas] = useState<Record<string, { name: string; type: string }[]>>({});

  const load = async () => {
    setLoading(true);
    try {
      const data = await listComputations();
      setItems(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      // surface minimally; could wire into global error toast
      console.error('Failed to load computations:', message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { 
    load(); 
    // load examples/help
    (async () => {
      try {
        const info = await fetchComputationExamples();
        setSources(info.sources);
        setExamples(info.examples);
        setDslOps(info.dsl?.ops ?? []);
      } catch (e) {
        console.warn('Failed to fetch examples:', e);
      }
      try {
        const s = await fetchComputationSchemas();
        setSchemas(s.schemas || {});
      } catch (e) {
        console.warn('Failed to fetch schemas:', e);
      }
    })();
  }, []);

  const openNew = () => {
    const base = { ...empty };
    setEditing(base);
    setShow(true);
  };
  const openEdit = (it: ComputationDef) => {
    setEditing({ ...it });
    setShow(true);
  };
  const close = () => { setShow(false); setEditing(null); };

  const save = async () => {
    if (!editing) return;
    try {
      if (editing.id) await updateComputation(editing.id, editing);
      else await createComputation(editing);
      close();
      await load();
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      alert(message);
    }
  };

  const doDelete = async (id?: number) => {
    if (!id) return;
    if (!window.confirm('Delete computation?')) return;
    await deleteComputation(id);
    await load();
  };

  const doPreview = async (id?: number) => {
    if (!id) return;
    setPreviewData(null);
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const rows = await previewComputation(id);
      setPreviewData(rows ?? []);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : String(e);
      alert(message);
      setPreviewOpen(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  return (
    <div className="container pt-3 pb-4">
      <PageHeader title="Computations" right={<Button onClick={openNew}>New</Button>} />
      <Card className="shadow-sm border-body">
        <Card.Body>
          {sources.length > 0 && (
            <div className="mb-3 small text-body-secondary">
              <strong>Sources:</strong> {sources.join(', ')}
              {dslOps.length > 0 && (
                <span className="ms-3">
                  <strong>Ops:</strong> {dslOps.join(', ')}
                </span>
              )}
            </div>
          )}
          <ComputationsTable
            items={items}
            isDark={isDark}
            loading={loading}
            onEdit={openEdit}
            onPreview={doPreview}
            onDelete={doDelete}
          />
        </Card.Body>
      </Card>
      <EditorModal
        show={show}
        editing={editing}
        setEditing={(updater) => setEditing((prev) => updater(prev))}
        sources={sources}
        examples={examples}
        schemas={schemas}
        onClose={close}
        onSave={save}
      />

      <PreviewModal
        open={previewOpen}
        loading={previewLoading}
        data={previewData}
        onClose={() => {
          setPreviewOpen(false);
          setPreviewData(null);
        }}
      />
    </div>
  );
};

export default ComputationsPage;
