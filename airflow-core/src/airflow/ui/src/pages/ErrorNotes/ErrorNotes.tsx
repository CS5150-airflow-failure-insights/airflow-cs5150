/*!
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { Box, Button as ChakraButton, Flex, HStack, Text, VStack } from "@chakra-ui/react";
import type { ColumnDef } from "@tanstack/react-table";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuthLinksServiceGetCurrentUserInfo } from "openapi/queries";
import { DataTable } from "src/components/DataTable";
import { ErrorAlert } from "src/components/ErrorAlert";
import { SearchBar } from "src/components/SearchBar";
import { Dialog, toaster } from "src/components/ui";
import { Tooltip } from "src/components/ui/Tooltip";
import DeleteDialog from "src/components/DeleteDialog";
import { TrimText } from "src/utils/TrimText";

interface ErrorNoteRow {
  note_id: number;
  author: string;
  note_text: string;
  external_url: string | null;
  signature_canonical: string;
  signature_regex: string;
  created_at: string;
}

const getColumns = ({
  translate,
  currentUsername,
  onEdit,
  onDelete,
}: {
  translate: TFunction;
  currentUsername: string;
  onEdit: (note: ErrorNoteRow) => void;
  onDelete: (note: ErrorNoteRow) => void;
}): Array<ColumnDef<ErrorNoteRow>> => {
  return [
    {
      accessorKey: "signature_canonical",
      cell: ({ row }) => (
        <TrimText showTooltip text={row.original.signature_canonical} />
      ),
      enableSorting: false,
      header: translate("errorNotes.columns.matchedError"),
    },
    {
      accessorKey: "note_text",
      cell: ({ row }) => <TrimText showTooltip text={row.original.note_text} />,
      enableSorting: false,
      header: translate("errorNotes.columns.note"),
    },
    {
      accessorKey: "author",
      cell: ({ row }) => <Text>{row.original.author}</Text>,
      enableSorting: false,
      header: translate("errorNotes.columns.author"),
    },
    {
      accessorKey: "created_at",
      cell: ({ row }) => (
        <Text>{new Date(row.original.created_at).toLocaleDateString()}</Text>
      ),
      enableSorting: false,
      header: translate("errorNotes.columns.dateAdded"),
    },
    {
      accessorKey: "external_url",
      cell: ({ row }) => {
        if (row.original.external_url) {
          return (
            <Tooltip content={row.original.external_url} portalled>
              <a
                href={row.original.external_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: "var(--chakra-colors-blue-600)", cursor: "pointer" }}
              >
                🔗
              </a>
            </Tooltip>
          );
        }
        return <Text>—</Text>;
      },
      enableSorting: false,
      header: translate("errorNotes.columns.link"),
    },
    {
      accessorKey: "actions",
      cell: ({ row: { original } }) => {
        const canEdit = currentUsername === original.author;
        return (
          <Flex justifyContent="end" gap={2}>
            <ChakraButton
              size="sm"
              variant={canEdit ? "outline" : "ghost"}
              onClick={() => onEdit(original)}
              disabled={!canEdit}
            >
              {canEdit ? "Edit" : "View"}
            </ChakraButton>
            {canEdit && (
              <ChakraButton
                size="sm"
                variant="outline"
                colorPalette="red"
                onClick={() => onDelete(original)}
              >
                Delete
              </ChakraButton>
            )}
          </Flex>
        );
      },
      enableSorting: false,
      header: translate("errorNotes.columns.actions"),
    },
  ];
};

export const ErrorNotes = () => {
  const { t: translate } = useTranslation("admin");
  const { data: currentUser } = useAuthLinksServiceGetCurrentUserInfo();
  const currentUsername = currentUser?.username?.trim() ?? "";

  const [searchTerm, setSearchTerm] = useState("");
  const [showMyNotesOnly, setShowMyNotesOnly] = useState(false);
  const [editingNote, setEditingNote] = useState<ErrorNoteRow | null>(null);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editedNoteText, setEditedNoteText] = useState("");
  const [editedUrl, setEditedUrl] = useState("");
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deletingNote, setDeletingNote] = useState<ErrorNoteRow | null>(null);

  const queryClient = useQueryClient();

  const { data, error, isFetching, isLoading } = useQuery({
    queryKey: ["errorNotes"],
    queryFn: async () => {
      const response = await axios.get("/ui/error-notes");
      return response.data.notes as ErrorNoteRow[];
    },
  });

  // Filter notes based on search term and "My notes" toggle
  const filteredNotes = (data || []).filter((note) => {
    const matchesSearch =
      !searchTerm ||
      note.signature_canonical.toLowerCase().includes(searchTerm.toLowerCase()) ||
      note.note_text.toLowerCase().includes(searchTerm.toLowerCase());

    const matchesMyNotes = !showMyNotesOnly || note.author === currentUsername;

    return matchesSearch && matchesMyNotes;
  });

  const { isPending: isUpdating, mutate: updateNote } = useMutation({
    mutationFn: async ({
      noteId,
      noteText,
      externalUrl,
    }: {
      noteId: number;
      noteText: string;
      externalUrl: string | null;
    }) =>
      axios.patch(`/ui/error-notes/${noteId}`, {
        note_text: noteText,
        external_url: externalUrl,
      }),
    onError: () => {
      toaster.create({
        description: "Failed to update note.",
        title: "Update failed",
        type: "error",
      });
    },
    onSuccess: () => {
      toaster.create({
        description: "Note updated successfully.",
        title: "Note updated",
        type: "success",
      });
      setIsEditModalOpen(false);
      setEditingNote(null);
      queryClient.invalidateQueries({ queryKey: ["errorNotes"] });
    },
  });

  const { isPending: isDeleting, mutate: deleteNote } = useMutation({
    mutationFn: async (noteId: number) => axios.delete(`/ui/error-notes/${noteId}`),
    onError: () => {
      toaster.create({
        description: "Failed to delete note.",
        title: "Delete failed",
        type: "error",
      });
    },
    onSuccess: () => {
      toaster.create({
        description: "Note deleted successfully.",
        title: "Note deleted",
        type: "success",
      });
      setDeleteConfirmOpen(false);
      setDeletingNote(null);
      queryClient.invalidateQueries({ queryKey: ["errorNotes"] });
    },
  });

  const handleEdit = (note: ErrorNoteRow) => {
    setEditingNote(note);
    setEditedNoteText(note.note_text);
    setEditedUrl(note.external_url || "");
    setIsEditModalOpen(true);
  };

  const handleSaveEdit = () => {
    if (!editingNote || !editedNoteText.trim()) {
      toaster.create({
        description: "Note text cannot be empty.",
        title: "Validation error",
        type: "error",
      });
      return;
    }

    updateNote({
      noteId: editingNote.note_id,
      noteText: editedNoteText.trim(),
      externalUrl: editedUrl.trim() || null,
    });
  };

  const handleDeleteClick = (note: ErrorNoteRow) => {
    setDeletingNote(note);
    setDeleteConfirmOpen(true);
  };

  const handleConfirmDelete = () => {
    if (deletingNote) {
      deleteNote(deletingNote.note_id);
    }
  };

  const columns = getColumns({
    translate,
    currentUsername,
    onEdit: handleEdit,
    onDelete: handleDeleteClick,
  });

  return (
    <VStack alignItems="flex-start" gap={4} p={6}>
      <Box>
        <Text fontSize="2xl" fontWeight="bold" mb={1}>
          {translate("errorNotes.title")}
        </Text>
        <Text fontSize="sm" color="gray.600">
          {translate("errorNotes.description")}
        </Text>
      </Box>

      <HStack gap={4} width="100%">
        <SearchBar
          onChange={setSearchTerm}
          placeholder={translate("errorNotes.searchPlaceholder")}
          defaultValue={searchTerm}
        />
        <HStack>
          <input
            type="checkbox"
            checked={showMyNotesOnly}
            onChange={(e) => setShowMyNotesOnly(e.target.checked)}
          />
          <Text fontSize="sm">{translate("errorNotes.myNotesOnly")}</Text>
        </HStack>
      </HStack>

      <ErrorAlert error={error} />

      <DataTable
        columns={columns as any}
        data={filteredNotes}
        isFetching={isFetching}
        isLoading={isLoading}
        modelName="error_notes"
      />

      {/* Edit Modal */}
      <Dialog.Root open={isEditModalOpen} onOpenChange={(details: any) => setIsEditModalOpen(details.open)} size="md">
        <Dialog.Content>
          <Dialog.Header>
            <Text fontSize="lg" fontWeight="semibold">
              Edit Error Note
            </Text>
          </Dialog.Header>
          <Dialog.CloseTrigger />
          <Dialog.Body gap={4} display="flex" flexDirection="column">
            <Box>
              <Text fontSize="xs" fontWeight="medium" mb={2} textTransform="uppercase">
                Matched Error
              </Text>
              <Text fontSize="sm" color="gray.700" p={2} bg="gray.50" borderRadius="md">
                {editingNote?.signature_canonical}
              </Text>
            </Box>
            <Box>
              <Text fontSize="xs" fontWeight="medium" mb={2} textTransform="uppercase">
                Note
              </Text>
              <textarea
                value={editedNoteText}
                onChange={(e) => setEditedNoteText(e.target.value)}
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: "4px",
                  border: "1px solid var(--chakra-colors-gray-200)",
                  fontFamily: "inherit",
                  minHeight: "120px",
                }}
              />
            </Box>
            <Box>
              <Text fontSize="xs" fontWeight="medium" mb={2} textTransform="uppercase">
                Reference Link (optional)
              </Text>
              <input
                type="url"
                value={editedUrl}
                onChange={(e) => setEditedUrl(e.target.value)}
                placeholder="https://example.com/docs"
                style={{
                  width: "100%",
                  padding: "8px",
                  borderRadius: "4px",
                  border: "1px solid var(--chakra-colors-gray-200)",
                  fontFamily: "inherit",
                }}
              />
            </Box>
          </Dialog.Body>
          <Dialog.Footer>
            <HStack gap={2}>
              <ChakraButton variant="outline" onClick={() => setIsEditModalOpen(false)}>
                Cancel
              </ChakraButton>
              <ChakraButton
                colorPalette="blue"
                onClick={handleSaveEdit}
                disabled={isUpdating || !editedNoteText.trim()}
              >
                Save
              </ChakraButton>
            </HStack>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Root>

      {/* Delete Confirmation Dialog */}
      <DeleteDialog
        isDeleting={isDeleting}
        onClose={() => {
          setDeleteConfirmOpen(false);
          setDeletingNote(null);
        }}
        onDelete={handleConfirmDelete}
        open={deleteConfirmOpen}
        resourceName="error note"
        title="Delete Error Note"
        warningText="This action cannot be undone."
      />
    </VStack>
  );
};
