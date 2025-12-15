import React, { useState, useEffect } from 'react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import DashboardLayout from '../layouts/DashboardLayout';
import api from '../lib/api';
import { PhoneIcon, ClockIcon, CheckCircleIcon, XCircleIcon, ExclamationTriangleIcon, UserIcon, EnvelopeIcon, CalendarIcon } from '@heroicons/react/24/outline'
import { Link } from 'react-router-dom';
import { useTranslation } from '../lib/translations';
import toast from 'react-hot-toast';

interface CallbackRequest {
  id: number;
  call_id: number;
  agent_id: number;
  reason: string;
  priority: string;
  caller_name: string | null;
  caller_phone: string | null;
  caller_email: string | null;
  preferred_callback_time: string | null;
  status: string;
  assigned_to: string | null;
  notes: string | null;
  resolution: string | null;
  created_at: string;
  contacted_at: string | null;
  completed_at: string | null;
}

export const CallbacksPage: React.FC = () => {
  const t = useTranslation();
  const [callbacks, setCallbacks] = useState<CallbackRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [updateLoading, setUpdateLoading] = useState(false);
  const [filter, setFilter] = useState<string>('all');
  const [selectedCallback, setSelectedCallback] = useState<CallbackRequest | null>(null);
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  const [updateData, setUpdateData] = useState({
    status: '',
    assigned_to: '',
    notes: '',
    resolution: ''
  });

  useEffect(() => {
    loadCallbacks();
  }, [filter]);

  const loadCallbacks = async () => {
    try {
      const params: any = {};
      if (filter !== 'all') {
        params.status_filter = filter;
      }
      const response = await api.get('/callbacks/', { params });
      setCallbacks(response.data);
    } catch (error) {
      console.error('Error loading callbacks:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateCallback = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedCallback) return;

    setUpdateLoading(true);
    try {
      await api.patch(`/callbacks/${selectedCallback.id}`, updateData);
      await loadCallbacks();
      setShowUpdateModal(false);
      setSelectedCallback(null);
      toast.success(t.callbacks.updateSuccess);
    } catch (error: any) {
      toast.error(t.callbacks.updateError + ': ' + (error.response?.data?.detail || error.message));
    } finally {
      setUpdateLoading(false);
    }
  };

  const getPriorityBadge = (priority: string) => {
    const colors: Record<string, string> = {
      urgent: 'bg-red-600',
      high: 'bg-orange-500',
      normal: 'bg-blue-500',
      low: 'bg-gray-500'
    };

    const emoji: Record<string, string> = {
      urgent: '🚨',
      high: '⚠️',
      normal: '📞',
      low: '📝'
    };

    return (
      <Badge className={colors[priority] || 'bg-gray-500'}>
        {emoji[priority]} {priority.toUpperCase()}
      </Badge>
    );
  };

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-yellow-500',
      contacted: 'bg-blue-500',
      completed: 'bg-green-500',
      cancelled: 'bg-gray-500'
    };

    return (
      <Badge className={colors[status] || 'bg-gray-500'}>
        {status.toUpperCase()}
      </Badge>
    );
  };

  if (loading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          {/* Header - Keep static */}
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t.callbacks.callbackRequests}</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">
                {t.callbacks.manageCallbacks}
              </p>
            </div>
          </div>

          {/* Filter tabs - Keep static */}
          <div className="flex space-x-1 bg-gray-100 dark:bg-gray-800 p-1 rounded-lg">
            {['all', 'pending', 'contacted', 'completed', 'cancelled'].map((status) => (
              <button
                key={status}
                className="px-4 py-2 text-sm font-medium rounded-md bg-gray-200 dark:bg-gray-700 animate-pulse"
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>

          {/* Loading skeleton for callbacks */}
          <div className="grid gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Card key={i}>
                <div className="flex items-start justify-between">
                  <div className="flex items-center space-x-4">
                    <div className="p-3 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse">
                      <div className="w-6 h-6 bg-gray-300 dark:bg-gray-600 rounded"></div>
                    </div>
                    <div className="space-y-2">
                      <div className="h-5 w-40 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                      <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                      <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                    </div>
                  </div>
                  <div className="text-right space-y-2">
                    <div className="h-6 w-16 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse"></div>
                    <div className="h-6 w-20 bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse"></div>
                    <div className="h-8 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse"></div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t.callbacks.callbackRequests}</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">
            {t.callbacks.manageCallbacks}
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2">
        <Button
          variant={filter === 'all' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('all')}
        >
          {t.callbacks.all}
        </Button>
        <Button
          variant={filter === 'pending' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('pending')}
        >
          {t.callbacks.pending}
        </Button>
        <Button
          variant={filter === 'contacted' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('contacted')}
        >
          {t.callbacks.contacted}
        </Button>
        <Button
          variant={filter === 'completed' ? 'default' : 'outline'}
          size="sm"
          onClick={() => setFilter('completed')}
        >
          {t.callbacks.completed}
        </Button>
      </div>

      {/* Callbacks List */}
      {callbacks.length === 0 ? (
        <Card>
          <div className="text-center py-12">
            <PhoneIcon className="mx-auto h-12 w-12 text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900 dark:text-white">
              {t.callbacks.noCallbackRequests}
            </h3>
            <p className="mt-2 text-gray-600 dark:text-gray-400">
              {t.callbacks.noCallbackRequestsDesc}
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid gap-4">
          {callbacks.map((callback) => (
            <Card key={callback.id}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-3 mb-3">
                    {getPriorityBadge(callback.priority)}
                    {getStatusBadge(callback.status)}
                    <span className="text-sm text-gray-500">
                      {t.callbacks.createdAt}: {new Date(callback.created_at).toLocaleString()}
                    </span>
                  </div>

                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                    {callback.reason}
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
                    {callback.caller_name && (
                      <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <UserIcon className="h-4 w-4" />
                        <span>{callback.caller_name}</span>
                      </div>
                    )}
                    {callback.caller_phone && (
                      <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <PhoneIcon className="h-4 w-4" />
                        <span>{callback.caller_phone}</span>
                      </div>
                    )}
                    {callback.caller_email && (
                      <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <EnvelopeIcon className="h-4 w-4" />
                        <span>{callback.caller_email}</span>
                      </div>
                    )}
                    {callback.preferred_callback_time && (
                      <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                        <CalendarIcon className="h-4 w-4" />
                        <span>{t.callbacks.preferredCallbackTime}: {callback.preferred_callback_time}</span>
                      </div>
                    )}
                  </div>

                  {callback.notes && (
                    <div className="mb-3 p-3 bg-gray-50 dark:bg-gray-800 rounded-lg">
                      <p className="text-sm text-gray-700 dark:text-gray-300">
                        <strong>{t.callbacks.notes}:</strong> {callback.notes}
                      </p>
                    </div>
                  )}

                  {callback.resolution && (
                    <div className="mb-3 p-3 bg-green-50 dark:bg-green-900/20 rounded-lg">
                      <p className="text-sm text-green-700 dark:text-green-300">
                        <strong>{t.callbacks.resolution}:</strong> {callback.resolution}
                      </p>
                    </div>
                  )}

                  {callback.assigned_to && (
                    <div className="text-sm text-gray-600 dark:text-gray-400">
                      <strong>{t.callbacks.assignedTo}:</strong> {callback.assigned_to}
                    </div>
                  )}
                </div>

                <div className="flex flex-col gap-2 ml-4">
                  <Link to={`/dashboard/calls?callId=${callback.call_id}`}>
                    <Button variant="outline" size="sm">
                      {t.callbacks.viewCall}
                    </Button>
                  </Link>
                  {callback.status !== 'completed' && callback.status !== 'cancelled' && (
                    <Button
                      size="sm"
                      onClick={() => {
                        setSelectedCallback(callback);
                        setUpdateData({
                          status: callback.status,
                          assigned_to: callback.assigned_to || '',
                          notes: callback.notes || '',
                          resolution: callback.resolution || ''
                        });
                        setShowUpdateModal(true);
                      }}
                    >
                      {t.callbacks.update}
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Update Callback Modal */}
      {showUpdateModal && selectedCallback && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-2xl font-bold mb-4">{t.callbacks.updateCallbackRequest}</h2>
            <form onSubmit={handleUpdateCallback} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2">{t.callbacks.status}</label>
                <select
                  value={updateData.status}
                  onChange={(e) => setUpdateData({ ...updateData, status: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                >
                  <option value="pending">{t.callbacks.pending}</option>
                  <option value="contacted">{t.callbacks.contacted}</option>
                  <option value="completed">{t.callbacks.completed}</option>
                  <option value="cancelled">{t.callbacks.cancelled}</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t.callbacks.assignedTo}</label>
                <input
                  type="text"
                  value={updateData.assigned_to}
                  onChange={(e) => setUpdateData({ ...updateData, assigned_to: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  placeholder={t.callbacks.assignedToPlaceholder}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t.callbacks.notes}</label>
                <textarea
                  value={updateData.notes}
                  onChange={(e) => setUpdateData({ ...updateData, notes: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  rows={3}
                  placeholder={t.callbacks.notesPlaceholder}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-2">{t.callbacks.resolution}</label>
                <textarea
                  value={updateData.resolution}
                  onChange={(e) => setUpdateData({ ...updateData, resolution: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg dark:bg-gray-800 dark:border-gray-700"
                  rows={3}
                  placeholder={t.callbacks.resolutionPlaceholder}
                />
              </div>

              <div className="flex gap-3 pt-4">
                <Button type="submit" className="flex-1" disabled={updateLoading}>
                  {updateLoading ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      {t.callbacks.updating}
                    </>
                  ) : (
                    <>
                      <CheckCircleIcon className="mr-2 h-4 w-4" />
                      {t.callbacks.updateButton}
                    </>
                  )}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setShowUpdateModal(false);
                    setSelectedCallback(null);
                  }}
                  className="flex-1"
                >
                  {t.common.cancel}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
      </div>
    </DashboardLayout>
  );
};

