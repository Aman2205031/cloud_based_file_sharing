document.getElementById('upload-form').addEventListener('submit', function (e) {
  e.preventDefault();
  const fileInput = document.getElementById('file-input');
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);

  fetch('/upload', {
    method: 'POST',
    body: formData
  })
  .then(response => response.json())
  .then(data => {
    const messageDiv = document.getElementById('upload-message');
    if (data.success) {
      messageDiv.textContent = '✅ File uploaded successfully!';
      messageDiv.style.color = 'green';
      fileInput.value = ''; 
      fetchFiles(); 
    } else {
      messageDiv.textContent = `❌ ${data.error}`;
      messageDiv.style.color = 'red';
    }
  })
  .catch(error => {
    alert('❌ Error uploading file');
    console.error('Upload Error:', error);
  });
});

function deleteFile(filename) {
  if (confirm(`Are you sure you want to delete "${filename}"?`)) {
    fetch(`/delete/${filename}`, {
      method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
      alert(data.message || 'Deleted!');
      const safeId = `file-${filename.replace(/\s+/g, '_').replace(/[^\w\-]/g, '')}`;
      const fileCard = document.getElementById(safeId);
      if (fileCard) fileCard.remove();
    })
    .catch(err => {
      alert('❌ Error deleting file');
      console.error(err);
    });
  }
}

function downloadFile(filename) {
  fetch(`/download/${filename}`)
    .then(res => res.json())
    .then(data => {
      if (data.file_url) {
        window.open(data.file_url, '_blank');
      } else {
        alert("❌ Download link couldn't be generated.");
      }
    })
    .catch(err => {
      alert("❌ Error downloading file");
      console.error(err);
    });
}


function previewFile(filename) {
  fetch(`/preview/${filename}`)
    .then(response => response.json())
    .then(data => {
      if (data.file_url) {
        window.open(data.file_url, "_blank");
      } else {
        alert("❌ File preview not available.");
      }
    })
    .catch(err => {
      alert("❌ Error previewing file");
      console.error(err);
    });
}

