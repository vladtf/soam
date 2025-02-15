import React from 'react';
import { Container, Row, Col } from 'react-bootstrap';
import { FaGithub } from 'react-icons/fa';

const AppFooter: React.FC = () => {
    return (
        <Container>
            <Row>
                <Col >
                    <footer className="bg-dark text-white mt-5 p-2">
                        <a href="https://github.com/vladtf/soam" target="_blank" rel="noopener noreferrer" className="text-white">
                            <FaGithub /><span className="ms-2">Repository</span>
                        </a>
                    </footer>
                </Col>
            </Row>
        </Container>
    );
};

export default AppFooter;
