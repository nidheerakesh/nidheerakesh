function Task({ title, onDelete }) {
    return (
      <li style={{ margin: '1rem 0' }}>
        {title}
        <button
          style={{ marginLeft: '1rem', backgroundColor: 'crimson' }}
          onClick={onDelete}
        >
          Delete
        </button>
      </li>
    );
  }
  
  export default Task;
  